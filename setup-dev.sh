#!/bin/bash

echo "🔧 Covenantrix Development Setup"
echo ""

echo "📦 Installing Node.js dependencies..."
npm install

echo ""
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment and installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo ""
echo "🏗️ Building Python service executable for development..."
pip install pyinstaller
pyinstaller covenantrix-service.spec --noconfirm --clean

if [ -f "dist/covenantrix-service" ]; then
    echo "Moving executable to python-dist directory..."
    mkdir -p python-dist
    mv dist/covenantrix-service python-dist/
    chmod +x python-dist/covenantrix-service
    rm -rf dist/
    echo "✅ Python service executable built successfully"
else
    echo "⚠️  Python executable build failed, will use venv fallback"
fi

echo ""
echo "🚀 Development setup complete!"
echo "You can now run: npm run dev"
