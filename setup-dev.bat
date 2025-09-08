@echo off
echo 🔧 Covenantrix Development Setup
echo.

echo 📦 Installing Node.js dependencies...
call npm install

echo.
echo 🐍 Setting up Python environment...
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment and installing Python dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo 🏗️ Building Python service executable for development...
pip install pyinstaller
pyinstaller covenantrix-service.spec --noconfirm --clean

if exist dist\covenantrix-service.exe (
    echo Moving executable to python-dist directory...
    if not exist python-dist mkdir python-dist
    move dist\covenantrix-service.exe python-dist\
    rmdir /s /q dist
    echo ✅ Python service executable built successfully
) else (
    echo ⚠️  Python executable build failed, will use venv fallback
)

echo.
echo 🚀 Development setup complete!
echo You can now run: npm run dev
