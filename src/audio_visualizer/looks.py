"""User custom visual looks ("My Looks"), persisted as JSON.

A *look* is a saved snapshot of a complete visual look — the mode and its option
indices, the theme, sensitivity/smoothing, and the Background/Logo state — that
the user can re-select later from the ``My Looks`` dropdown.

Storage mirrors :mod:`settings` deliberately: a separate ``looks.json`` under
``%APPDATA%\\AudioVisualizer`` (so a malformed look can never corrupt core
settings), an atomic best-effort save, and a lenient load that never raises.
Key differences from settings: the payload is a **list**, so each look is
validated independently and one bad entry is skipped rather than discarding the
file; and unrecognized keys are preserved per-look (``extra``) and re-emitted on
save, so an older build re-saving a newer file does not silently drop fields.

This module is pure data + I/O (no pygame, no app state) so it stays unit-testable.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from audio_visualizer.config import (
    APP_VERSION,
    LOOK_NAME_MAX,
    LOOKS_FILENAME,
    LOOKS_MAX,
    LOOKS_SCHEMA_VERSION,
)
from audio_visualizer.platform_win import get_appdata_dir

logger = logging.getLogger(__name__)

# Background/Logo domains may either snapshot their values into the look
# ("local") or follow whatever the user's live global is ("global").
LINK_LOCAL = "local"
LINK_GLOBAL = "global"
_LINKS = (LINK_LOCAL, LINK_GLOBAL)

# Fields owned by the dataclass; any other key in a stored record is unknown and
# round-tripped via ``Look.extra`` for forward compatibility.
_KNOWN_KEYS = frozenset(
    {
        "id",
        "name",
        "base_mode_key",
        "options",
        "theme",
        "sensitivity",
        "smoothing",
        "background",
        "logo",
        "created_at",
        "updated_at",
        "app_version",
        "readonly",
    }
)


def new_id() -> str:
    """A fresh, stable look id (uuid4 hex)."""
    return uuid.uuid4().hex


def _now() -> str:
    """Current UTC timestamp, ISO 8601 with a trailing ``Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_name(name: object, fallback: str = "Untitled") -> str:
    """Trim/limit a user-supplied look name; fall back when empty/invalid."""
    text = name.strip() if isinstance(name, str) else ""
    text = " ".join(text.split())  # collapse internal whitespace runs
    if not text:
        return fallback
    return text[:LOOK_NAME_MAX]


@dataclass
class Look:
    """One saved look. ``id`` is stable; ``name`` is user-editable.

    The captured payload (mode/options/theme/sensitivity/smoothing) is always a
    local snapshot. ``background``/``logo`` each carry a ``link`` (``local`` ⇒
    snapshot in ``value``; ``global`` ⇒ follow live global, no value stored).
    """

    id: str
    name: str
    base_mode_key: str
    options: dict[str, int] = field(default_factory=dict)
    theme: dict[str, object] = field(default_factory=dict)
    sensitivity: float = 1.0
    smoothing: float = 0.5
    background: dict[str, object] = field(default_factory=lambda: {"link": LINK_LOCAL})
    logo: dict[str, object] = field(default_factory=lambda: {"link": LINK_LOCAL})
    created_at: str = ""
    updated_at: str = ""
    app_version: str = ""
    readonly: bool = False
    # Unrecognized keys from a newer schema, re-emitted verbatim on save.
    extra: dict[str, object] = field(default_factory=dict)

    def payload(self) -> dict[str, object]:
        """The captured look only (no id/name/metadata) for dirty comparison."""
        return {
            "base_mode_key": self.base_mode_key,
            "options": dict(self.options),
            "theme": dict(self.theme),
            "sensitivity": self.sensitivity,
            "smoothing": self.smoothing,
            "background": dict(self.background),
            "logo": dict(self.logo),
        }

    def matches_payload(self, other: Look) -> bool:
        """True when the captured looks are identical (ignores id/name/time)."""
        return self.payload() == other.payload()


def to_json(look: Look) -> dict[str, object]:
    """Serialize a look. Read-only (starter) looks are never persisted."""
    data: dict[str, object] = {
        "id": look.id,
        "name": look.name,
        "base_mode_key": look.base_mode_key,
        "options": dict(look.options),
        "theme": dict(look.theme),
        "sensitivity": look.sensitivity,
        "smoothing": look.smoothing,
        "background": dict(look.background),
        "logo": dict(look.logo),
        "created_at": look.created_at,
        "updated_at": look.updated_at,
        "app_version": look.app_version,
    }
    # Re-emit unknown future keys (forward-compat), but never let them shadow
    # fields we own.
    for key, value in look.extra.items():
        if key not in _KNOWN_KEYS:
            data[key] = value
    return data


def _domain(raw: object) -> dict[str, object]:
    """Validate a Background/Logo domain dict ({link, value?})."""
    if not isinstance(raw, dict):
        return {"link": LINK_LOCAL}
    link = raw.get("link")
    link = link if isinstance(link, str) and link in _LINKS else LINK_LOCAL
    out: dict[str, object] = {"link": link}
    if link == LINK_LOCAL and isinstance(raw.get("value"), dict):
        out["value"] = dict(raw["value"])
    return out


def _from_json(raw: object) -> Look | None:
    """Build a Look from one stored record; ``None`` if structurally invalid."""
    if not isinstance(raw, dict):
        return None
    mode = raw.get("base_mode_key")
    if not isinstance(mode, str) or not mode:
        return None  # a look with no base mode is meaningless; skip it
    look_id = raw.get("id")
    look_id = look_id if isinstance(look_id, str) and look_id else new_id()

    options = raw.get("options")
    options = (
        {
            k: int(v)
            for k, v in options.items()
            if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool)
        }
        if isinstance(options, dict)
        else {}
    )

    extra = {k: v for k, v in raw.items() if k not in _KNOWN_KEYS}
    return Look(
        id=look_id,
        name=sanitize_name(raw.get("name")),
        base_mode_key=mode,
        options=options,
        theme=dict(raw["theme"]) if isinstance(raw.get("theme"), dict) else {},
        sensitivity=_num(raw.get("sensitivity"), 1.0),
        smoothing=_num(raw.get("smoothing"), 0.5),
        background=_domain(raw.get("background")),
        logo=_domain(raw.get("logo")),
        created_at=_text(raw.get("created_at")),
        updated_at=_text(raw.get("updated_at")),
        app_version=_text(raw.get("app_version")),
        readonly=False,  # never trust a persisted readonly flag; only code ships those
        extra=extra,
    )


def _num(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


class LooksStore:
    """An ordered list of user looks with CRUD + library management.

    Order is the dropdown order. All mutators keep ids unique and enforce the
    ``LOOKS_MAX`` cap; none raise.
    """

    def __init__(self, looks: list[Look] | None = None) -> None:
        self._looks: list[Look] = []
        for look in looks or []:
            self._looks.append(look)
        self._dedupe_ids()

    # -- queries --------------------------------------------------------------
    @property
    def looks(self) -> list[Look]:
        """The looks in display order (live list; treat as read-only)."""
        return self._looks

    def get(self, look_id: str) -> Look | None:
        return next((look for look in self._looks if look.id == look_id), None)

    def index_of(self, look_id: str) -> int:
        return next((i for i, look in enumerate(self._looks) if look.id == look_id), -1)

    def name_exists(self, name: str, *, ignore_id: str = "") -> bool:
        target = sanitize_name(name)
        return any(look.name == target and look.id != ignore_id for look in self._looks)

    # -- mutators -------------------------------------------------------------
    def add(self, look: Look) -> Look | None:
        """Append a look (assigning a fresh id if it collides). ``None`` if full."""
        if len(self._looks) >= LOOKS_MAX:
            logger.warning("Looks limit (%d) reached; not adding %r", LOOKS_MAX, look.name)
            return None
        if not look.id or self.get(look.id) is not None:
            look = replace(look, id=new_id())
        look.name = sanitize_name(look.name)
        look.created_at = look.created_at or _now()
        look.updated_at = _now()
        look.app_version = look.app_version or APP_VERSION
        self._looks.append(look)
        return look

    def update(self, look_id: str, **changes: object) -> Look | None:
        """Overwrite fields of an existing look in place; bumps ``updated_at``."""
        look = self.get(look_id)
        if look is None or look.readonly:
            return None
        for key, value in changes.items():
            if hasattr(look, key):
                setattr(look, key, value)
        if "name" in changes:
            look.name = sanitize_name(look.name)
        look.updated_at = _now()
        return look

    def delete(self, look_id: str) -> bool:
        look = self.get(look_id)
        if look is None or look.readonly:
            return False
        self._looks.remove(look)
        return True

    def rename(self, look_id: str, name: str) -> bool:
        return self.update(look_id, name=name) is not None

    def duplicate(self, look_id: str) -> Look | None:
        """Clone a look right after the source with a fresh id and `" copy"` name."""
        src = self.get(look_id)
        if src is None or len(self._looks) >= LOOKS_MAX:
            return None
        clone = replace(
            src,
            id=new_id(),
            name=sanitize_name(f"{src.name} copy"),
            readonly=False,
            created_at=_now(),
            updated_at=_now(),
            options=dict(src.options),
            theme=dict(src.theme),
            background=dict(src.background),
            logo=dict(src.logo),
            extra=dict(src.extra),
        )
        self._looks.insert(self.index_of(look_id) + 1, clone)
        return clone

    def move(self, look_id: str, delta: int) -> bool:
        """Move a look up (delta<0) or down (delta>0) by one; clamps at the ends."""
        i = self.index_of(look_id)
        if i < 0:
            return False
        j = max(0, min(len(self._looks) - 1, i + delta))
        if i == j:
            return False
        self._looks.insert(j, self._looks.pop(i))
        return True

    def _dedupe_ids(self) -> None:
        seen: set[str] = set()
        for look in self._looks:
            if not look.id or look.id in seen:
                look.id = new_id()
            seen.add(look.id)

    # -- serialization --------------------------------------------------------
    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": LOOKS_SCHEMA_VERSION,
            "looks": [to_json(look) for look in self._looks if not look.readonly],
        }


def looks_path() -> Path:
    """Full path to the looks file under the app-data directory."""
    return get_appdata_dir() / LOOKS_FILENAME


def load(path: Path | None = None) -> LooksStore:
    """Load looks, skipping malformed entries; empty store on any file problem."""
    path = path or looks_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return LooksStore()
    except (OSError, ValueError):
        logger.warning("Looks file unreadable/corrupt; starting empty", exc_info=True)
        return LooksStore()

    if not isinstance(raw, dict) or not isinstance(raw.get("looks"), list):
        logger.warning("Looks file malformed; starting empty")
        return LooksStore()

    version = raw.get("schema_version")
    if version != LOOKS_SCHEMA_VERSION:
        logger.info("Migrating looks from schema %r to %d", version, LOOKS_SCHEMA_VERSION)

    looks: list[Look] = []
    for record in raw["looks"]:
        look = _from_json(record)
        if look is None:
            logger.warning("Skipping malformed look record")
            continue
        looks.append(look)
        if len(looks) >= LOOKS_MAX:
            break
    return LooksStore(looks)


def save(store: LooksStore, path: Path | None = None) -> bool:
    """Write looks atomically, keeping a ``.bak`` of the last good file."""
    path = path or looks_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                path.replace(path.with_suffix(path.suffix + ".bak"))
            except OSError:
                logger.debug("Could not refresh looks backup", exc_info=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(store.to_json(), indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        logger.warning("Could not save looks to %s", path, exc_info=True)
        return False


def export_look(look: Look, path: Path) -> bool:
    """Write a single look to ``path`` as a shareable ``.look.json`` file."""
    try:
        record = to_json(look)
        record["schema_version"] = LOOKS_SCHEMA_VERSION
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return True
    except OSError:
        logger.warning("Could not export look to %s", path, exc_info=True)
        return False


def import_look(path: Path) -> Look | None:
    """Read a single ``.look.json`` file. Always assigns a fresh id (never reuse)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read look file %s", path, exc_info=True)
        return None
    look = _from_json(raw)
    if look is None:
        return None
    return replace(look, id=new_id(), readonly=False)
