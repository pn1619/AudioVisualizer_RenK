@echo off
rem Wrapper so check-deps runs from cmd.exe / double-click. Forwards all args.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-deps.ps1" %*
