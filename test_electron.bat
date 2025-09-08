@echo off
echo 🚀 Starting Covenantrix Desktop Application Test
echo.

echo 📦 Installing Node.js dependencies...
call npm install

echo.
echo 🔧 Setting development environment...
set ELECTRON_IS_DEV=true

echo.
echo ⚡ Starting Electron application...
echo Press Ctrl+C to stop
echo.

call npm start

