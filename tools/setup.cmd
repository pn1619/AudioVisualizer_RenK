@echo off
rem Wrapper so setup runs from cmd.exe / double-click. Forwards all args.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
