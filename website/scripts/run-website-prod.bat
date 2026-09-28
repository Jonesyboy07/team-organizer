@echo off
if not exist "%~dp0..\static\dist\assets\dashboard.js" call "%~dp0build-frontend.bat"
if errorlevel 1 exit /b 1
py -m website.wsgi