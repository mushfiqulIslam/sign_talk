@echo off
rem Sign Talk gloves: double-click to start. First run sets everything up (about a minute).
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo Setting up for the first time: installing uv, a small Python manager...
  powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
uv run --python 3.12 signtalk-gloves run --name "%COMPUTERNAME%" %*
echo.
echo Sign Talk gloves stopped. If Windows asked about the firewall, allow it and start again.
pause
