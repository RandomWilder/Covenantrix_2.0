# Changelog

## [1.0.5] - 2025-09-08

### 🚀 Major Features
- **Unified Single-Command Startup**: Application now starts both frontend and backend with a single `npm start` command
- **Automatic Service Management**: Electron app automatically detects and starts Python backend service
- **Smart Fallback System**: Bundled executable → venv fallback → user dialog (development-to-production aligned)

### 🔧 Improvements
- **Enhanced Startup Logic**: Proactive service startup instead of reactive connection attempts
- **Cross-Platform Support**: Improved Windows/macOS/Linux compatibility for development paths
- **Development Tools**: Added comprehensive setup and testing scripts
- **Future-Proof Code**: Replaced deprecated FastAPI event handlers with modern lifespan handlers

### 🐛 Bug Fixes
- **Unicode Console Support**: Fixed Windows console encoding issues for emoji characters
- **Service Connection**: Eliminated blank Electron window issues in production
- **PyInstaller Bundling**: Added missing dependencies for proper executable creation

### 🛠️ Development Experience
- **New Scripts**:
  - `npm run setup-dev`: One-command development environment setup
  - `npm run test-startup`: Comprehensive startup testing
  - `npm run dev`: Alias for development mode
- **Setup Automation**: Cross-platform setup scripts (`setup-dev.bat`/`setup-dev.sh`)
- **Documentation**: Complete development guide in `DEV-SETUP.md`

### 📦 Technical Changes
- Updated PyInstaller spec with comprehensive hidden imports
- Enhanced error handling and logging throughout startup process  
- Improved service connection retry logic with configurable timeouts
- Added UTF-8 encoding support for Windows console output

### 🎯 User Experience
- **Non-Technical Users**: Install and run - no backend configuration required
- **Developers**: Single command development workflow
- **Production**: Seamless automatic startup identical to development

---

## Previous Versions
- **1.0.4**: Base functionality with manual backend startup
- **1.0.3**: Initial release version
