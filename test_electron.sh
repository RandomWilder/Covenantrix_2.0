#!/bin/bash

echo "🚀 Starting Covenantrix Desktop Application Test"
echo ""

echo "📦 Installing Node.js dependencies..."
npm install

echo ""
echo "🔧 Setting development environment..."
export ELECTRON_IS_DEV=true

echo ""
echo "⚡ Starting Electron application..."
echo "Press Ctrl+C to stop"
echo ""

npm start

