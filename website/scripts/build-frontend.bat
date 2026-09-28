@echo off
pushd "%~dp0..\frontend"
if not exist node_modules npm install
npm run build
popd