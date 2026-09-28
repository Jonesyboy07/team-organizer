@echo off
pushd "%~dp0..\.."
if errorlevel 1 exit /b 1
if not exist "website\static\dist\assets\dashboard.js" call "website\scripts\build-frontend.bat"
if errorlevel 1 (popd & exit /b 1)
py -m website.wsgi
popd