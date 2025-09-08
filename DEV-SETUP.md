# Development Setup Guide

## 🚀 Quick Start (Single Command)

For the easiest setup experience:

```bash
npm run setup-dev
```

This will:
- Install Node.js dependencies
- Set up Python virtual environment
- Install Python dependencies
- Build the Python service executable for local development
- Set up everything needed for unified startup

After setup, simply run:
```bash
npm start
# or
npm run dev
```

## 🔧 Manual Setup (If Needed)

### Windows:
```bash
# Run the setup script
setup-dev.bat

# Start development
npm start
```

### Linux/macOS:
```bash
# Make script executable and run
chmod +x setup-dev.sh
./setup-dev.sh

# Start development
npm start
```

## 📋 What's New?

### Unified Startup Experience
- **Single Command**: Just run `npm start` and everything works
- **Auto-Detection**: System automatically detects bundled executable vs venv fallback
- **No Manual Steps**: Python service starts automatically with Electron
- **Cross-Platform**: Same experience on Windows, macOS, and Linux

### Development vs Production Alignment
- **Development**: Tries bundled executable first, falls back to venv
- **Production**: Uses bundled executable from distribution
- **Same Code Path**: Both development and production use the same startup logic

### Error Handling
- **Graceful Fallbacks**: If bundled executable fails, automatically tries venv
- **Clear Logging**: Detailed console output shows what's happening
- **User Dialogs**: Only shown as last resort if all automatic attempts fail

## 🐛 Troubleshooting

### If Python Service Won't Start:
1. **Check Python Installation**: Ensure Python 3.9+ is installed
2. **Virtual Environment**: Make sure `venv` folder exists with dependencies
3. **Build Executable**: Run `npm run setup-dev` to rebuild the executable
4. **Check Console**: Electron dev tools show detailed startup logs

### If Electron Window is Blank:
- This should no longer happen with the new auto-startup logic
- If it does, check the Electron console for connection errors
- The system will automatically retry and show connection dialogs if needed

## 🏗️ Build Process

The system now supports:
- **Development Build**: `pyinstaller covenantrix-service.spec` (done by setup-dev)
- **Production Build**: Handled by GitHub Actions for distribution
- **Local Testing**: Can test with bundled executable identical to production

## 📁 File Structure After Setup

```
covenantrix-v2/
├── python-dist/                    # Local development executable
│   └── covenantrix-service.exe     # (Windows) or covenantrix-service (Unix)
├── venv/                           # Python virtual environment (fallback)
├── electron-app/                   # Electron frontend
└── core-rag-service/              # Python backend source
```

The system automatically detects which Python service to use based on availability.
