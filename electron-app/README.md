# Covenantrix Desktop Application

Modern Electron desktop app for AI-powered legal document analysis.

## 🏗️ Architecture

```
Electron Main Process (main.js)
    ↓ spawns
Python Service (127.0.0.1:8080)
    ↓ uses
Covenantrix RAG Engine
    ↓ communicates via
IPC Bridge (preload.js)
    ↓ to
React Renderer (index.html + renderer.js)
```

## 📁 Structure

```
electron-app/
├── src/
│   ├── main.js          # Electron main process
│   └── preload.js       # Security bridge
├── renderer/
│   ├── index.html       # UI layout
│   └── renderer.js      # Frontend logic
├── assets/
│   ├── icon.svg         # App icon (SVG)
│   └── icon.png         # App icon (PNG)
└── README.md           # This file
```

## 🚀 Features

### Core Functionality
- **Document Upload**: Drag & drop or file browser
- **Background Processing**: Non-blocking document analysis
- **Query Interface**: Natural language questions
- **AI Personas**: 5 specialized legal assistants
- **Query Modes**: 5 different analysis approaches

### UI/UX Features
- **Modern Interface**: Glassmorphism design
- **Real-time Status**: Service connection monitoring
- **Document Management**: Sidebar with processed documents
- **Response Display**: Formatted answers with confidence scores
- **Drag & Drop**: Intuitive file upload

### Security Features
- **Context Isolation**: Secure main-renderer communication
- **No Node Access**: Renderer process is sandboxed
- **IPC Bridge**: Controlled API access via preload script

## 🔧 Development

### Prerequisites
- Node.js 18+ 
- Python 3.9+ (for service)
- All Python dependencies from requirements.txt

### Setup
```bash
# Install Node.js dependencies
npm install

# Set development mode
export ELECTRON_IS_DEV=true  # Linux/Mac
set ELECTRON_IS_DEV=true     # Windows

# Start development
npm start
```

### Testing
```bash
# Windows
test_electron.bat

# Linux/Mac
./test_electron.sh
```

## 📋 API Communication

The renderer communicates with the Python service through:

1. **File Operations**
   - `selectFile()` - Open file dialog
   - `uploadFile(path, folderId)` - Upload document

2. **API Calls**
   - `apiCall(method, endpoint, data)` - Generic API wrapper
   - Pre-configured methods in `window.electronAPI.api`

3. **Service Events**
   - `onServiceReady()` - Service startup notification
   - `onMenuUploadDocument()` - Menu action handling

## 🎨 Theming

The app uses a modern glassmorphism design with:
- **Primary**: Purple gradient (#667eea to #764ba2)
- **Background**: Blurred glass panels
- **Typography**: System fonts with proper hierarchy
- **Interactions**: Smooth transitions and hover effects

## 🔍 Debugging

### Development Tools
- DevTools automatically open in development mode
- Console logging for all major operations
- Network tab shows Python service communication

### Common Issues
1. **Service not starting**: Check Python path and dependencies
2. **File upload fails**: Verify service connection
3. **Query timeout**: Check OpenAI API key

## 📦 Build Process

The app is configured for cross-platform builds:
- **Windows**: NSIS installer (.exe)
- **macOS**: DMG package (.dmg)
- **Linux**: AppImage portable (.AppImage)

Build commands are defined in the root package.json.
