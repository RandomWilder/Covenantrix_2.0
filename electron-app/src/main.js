// main.js - Electron main process
const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const path = require('path');
// No longer need child_process since we connect to existing service
const axios = require('axios');
const isDev = process.env.ELECTRON_IS_DEV === 'true';

class CovenantrixApp {
    constructor() {
        this.mainWindow = null;
        this.servicePort = 8080;
        this.serviceUrl = `http://127.0.0.1:${this.servicePort}`;
        this.pythonProcess = null;
    }

    async createWindow() {
        // Create the browser window
        this.mainWindow = new BrowserWindow({
            width: 1400,
            height: 900,
            minWidth: 1000,
            minHeight: 700,
            icon: path.join(__dirname, '../assets/icon.png'),
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                enableRemoteModule: false,
                preload: path.join(__dirname, 'preload.js')
            },
            titleBarStyle: 'default',
            show: false, // Don't show until ready
        });

        // Load the app - handle both development and packaged app paths
        const htmlPath = this.getHtmlFilePath();
        console.log(`📁 Loading HTML from: ${htmlPath}`);
        this.mainWindow.loadFile(htmlPath);
        
        if (isDev) {
            this.mainWindow.webContents.openDevTools();
        }

        // Show window when ready
        this.mainWindow.once('ready-to-show', () => {
            this.mainWindow.show();
            
            // Auto-start Python service first, then connect
            this.autoStartAndConnect();
        });

        // Handle window closed
        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });

        // Handle external links
        this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
            shell.openExternal(url);
            return { action: 'deny' };
        });
    }

    async connectToExistingService(maxAttempts = 30) {
        console.log('🔗 Connecting to existing Python service at 127.0.0.1:8080...');
        
        for (let i = 0; i < maxAttempts; i++) {
            try {
                const response = await axios.get(`${this.serviceUrl}/health`, { timeout: 1000 });
                if (response.status === 200) {
                    console.log('✅ Connected to Python service successfully!');
                    this.mainWindow.webContents.send('service-ready', this.serviceUrl);
                    return true;
                }
            } catch (error) {
                // Service not responding yet, wait and retry
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        console.error('❌ Could not connect to Python service');
        return false;
    }

    async autoStartAndConnect() {
        console.log('🚀 Auto-starting Covenantrix service...');
        
        // First, quickly check if service is already running
        try {
            const response = await axios.get(`${this.serviceUrl}/health`, { timeout: 2000 });
            if (response.status === 200) {
                console.log('✅ Service already running, connecting...');
                this.mainWindow.webContents.send('service-ready', this.serviceUrl);
                return;
            }
        } catch (error) {
            // Service not running, need to start it
            console.log('🔄 Service not running, starting automatically...');
        }
        
        // Automatically start the appropriate service
        const started = await this.startPythonService();
        if (!started) {
            console.error('❌ Failed to start Python service automatically');
            await this.showServiceConnectionOptions();
            return;
        }
        
        // Connect to the started service
        const connected = await this.connectToExistingService(20);
        if (!connected) {
            console.error('❌ Failed to connect after starting service');
            await this.showServiceConnectionOptions();
        }
    }

    async showServiceConnectionOptions() {
        const choice = await dialog.showMessageBox(this.mainWindow, {
            type: 'warning',
            title: 'Service Connection Failed',
            message: 'Cannot connect to the Covenantrix Python service at 127.0.0.1:8080.',
            detail: 'Choose how to proceed:',
            buttons: ['Start Service Automatically', 'Manual Instructions', 'Retry Connection'],
            defaultId: 0,
            cancelId: 2
        });

        switch (choice.response) {
            case 0: // Start automatically
                await this.startPythonService();
                break;
            case 1: // Manual instructions
                this.showServiceError();
                break;
            case 2: // Retry
                await this.connectToExistingService(10);
                break;
        }
    }

    async startPythonService() {
        console.log('🚀 Starting bundled Python service automatically...');
        const { spawn } = require('child_process');
        const path = require('path');
        const fs = require('fs');
        
        try {
            const executablePath = this.getPythonExecutablePath();
            
            if (!executablePath) {
                // Fallback to venv approach for development
                console.log('📋 Using venv fallback for development');
                return this.startPythonServiceVenvFallback();
            }
            
            console.log(`📁 Using bundled Python executable: ${executablePath}`);
            
            // Verify executable exists
            if (!fs.existsSync(executablePath)) {
                throw new Error(`Python executable not found at: ${executablePath}`);
            }
            
            // Set working directory to executable directory (for config.yaml)
            const workingDir = path.dirname(executablePath);
            
            // Start the bundled Python service
            this.pythonProcess = spawn(executablePath, [], {
                cwd: workingDir,
                stdio: ['ignore', 'pipe', 'pipe'],
                // Ensure executable permissions on Unix
                detached: false
            });
            
            this.pythonProcess.stdout.on('data', (data) => {
                console.log(`Python Service: ${data}`);
            });
            
            this.pythonProcess.stderr.on('data', (data) => {
                console.error(`Python Service Error: ${data}`);
            });
            
            this.pythonProcess.on('error', (error) => {
                console.error('Python Service Process Error:', error);
            });
            
            this.pythonProcess.on('exit', (code, signal) => {
                console.log(`Python Service exited with code ${code} and signal ${signal}`);
            });
            
            console.log('✅ Bundled Python service process started');
            return true;
            
        } catch (error) {
            console.error('Failed to start bundled Python service:', error);
            return false;
        }
    }

    startPythonServiceVenvFallback() {
        console.log('🔄 Falling back to venv Python service for development...');
        const { spawn } = require('child_process');
        const path = require('path');
        
        try {
            // Construct path to Python service (original venv approach)
            const projectRoot = path.join(__dirname, '../../');
            const venvBinDir = process.platform === 'win32' ? 'Scripts' : 'bin';
            const venvPythonExe = process.platform === 'win32' ? 'python.exe' : 'python';
            const venvPython = path.join(projectRoot, 'venv', venvBinDir, venvPythonExe);
            const serviceScript = path.join(projectRoot, 'core-rag-service', 'service_main.py');
            
            console.log(`🔧 Development fallback - using: ${venvPython}`);
            console.log(`📄 Service script: ${serviceScript}`);
            
            // Verify venv python exists
            const fs = require('fs');
            if (!fs.existsSync(venvPython)) {
                throw new Error(`Venv Python executable not found at: ${venvPython}`);
            }
            if (!fs.existsSync(serviceScript)) {
                throw new Error(`Service script not found at: ${serviceScript}`);
            }
            
            // Start the Python service with venv
            this.pythonProcess = spawn(venvPython, [serviceScript], {
                cwd: path.join(projectRoot, 'core-rag-service'),
                stdio: ['ignore', 'pipe', 'pipe']
            });
            
            this.pythonProcess.stdout.on('data', (data) => {
                console.log(`Python Service (venv): ${data}`);
            });
            
            this.pythonProcess.stderr.on('data', (data) => {
                console.error(`Python Service Error (venv): ${data}`);
            });
            
            this.pythonProcess.on('error', (error) => {
                console.error('Python Service Process Error (venv):', error);
            });
            
            this.pythonProcess.on('exit', (code, signal) => {
                console.log(`Python Service (venv) exited with code ${code} and signal ${signal}`);
            });
            
            console.log('✅ Venv Python service process started');
            return true;
            
        } catch (error) {
            console.error('Failed to start venv Python service:', error);
            return false;
        }
    }

    getPythonExecutablePath() {
        const path = require('path');
        const { app } = require('electron');
        
        // Determine if running in development or packaged app
        const isPackaged = app.isPackaged;
        console.log(`📦 App packaged: ${isPackaged}`);
        
        // Get platform-specific executable name
        const executableName = process.platform === 'win32' ? 'covenantrix-service.exe' : 'covenantrix-service';
        
        let executablePath;
        
        if (isPackaged) {
            // In packaged app: executable is in resources/python-service/
            if (process.platform === 'darwin') {
                // macOS: MyApp.app/Contents/Resources/python-service/
                executablePath = path.join(process.resourcesPath, 'python-service', executableName);
            } else {
                // Windows/Linux: MyApp/resources/python-service/  
                executablePath = path.join(process.resourcesPath, 'python-service', executableName);
            }
        } else {
            // In development: look for python-dist directory (created by PyInstaller locally)
            const projectRoot = path.join(__dirname, '../../');
            executablePath = path.join(projectRoot, 'python-dist', executableName);
            
            console.log(`🔧 Development mode - looking in: ${executablePath}`);
            
            // Check if bundled executable exists in development
            const fs = require('fs');
            if (!fs.existsSync(executablePath)) {
                console.log(`⚠️  Bundled executable not found in development, will try venv fallback`);
                return null; // Signal to use venv fallback
            }
        }
        
        console.log(`🎯 Target executable path: ${executablePath}`);
        return executablePath;
    }

    getHtmlFilePath() {
        const path = require('path');
        const { app } = require('electron');
        
        // Determine if running in development or packaged app
        const isPackaged = app.isPackaged;
        console.log(`📦 App packaged: ${isPackaged}`);
        
        let htmlPath;
        
        if (isPackaged) {
            // In packaged app: use app.getAppPath() for reliable path resolution
            const appPath = app.getAppPath();
            htmlPath = path.join(appPath, 'electron-app', 'build', 'index.html');
        } else {
            // In development: relative path from main.js location
            htmlPath = path.join(__dirname, '../build/index.html');
        }
        
        console.log(`🎯 HTML file path: ${htmlPath}`);
        return htmlPath;
    }

    showServiceError() {
        const isPackaged = app.isPackaged;
        
        if (isPackaged) {
            // User is running packaged app
            dialog.showErrorBox(
                'Service Startup Failed',
                'The Covenantrix analysis service failed to start.\n\nThis could be due to:\n• Antivirus software blocking the application\n• Missing system permissions\n• Corrupted installation\n\nTry restarting the application or reinstalling Covenantrix.\n\nIf the problem persists, please contact support.'
            );
        } else {
            // Developer is running in development mode
            dialog.showErrorBox(
                'Development Service Error',
                'Cannot start the bundled Python service.\n\nFor development:\n1. Build the Python executable first:\n   pyinstaller covenantrix-service.spec\n2. Or start the service manually:\n   cd core-rag-service\n   python service_main.py\n\nThe service should show "Uvicorn running on http://127.0.0.1:8080"'
            );
        }
    }

    disconnectFromService() {
        // Clean up Python process if we started it
        if (this.pythonProcess) {
            console.log('🔌 Stopping Python service...');
            this.pythonProcess.kill();
            this.pythonProcess = null;
        } else {
            console.log('🔌 Disconnecting from Python service (leaving it running)');
        }
    }

    createMenu() {
        const template = [
            {
                label: 'File',
                submenu: [
                    {
                        label: 'Upload Document',
                        accelerator: 'CmdOrCtrl+O',
                        click: () => {
                            this.mainWindow.webContents.send('menu-upload-document');
                        }
                    },
                    { type: 'separator' },
                    {
                        label: 'Exit',
                        accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
                        click: () => {
                            app.quit();
                        }
                    }
                ]
            },
            {
                label: 'View',
                submenu: [
                    { role: 'reload' },
                    { role: 'forceReload' },
                    { role: 'toggleDevTools' },
                    { type: 'separator' },
                    { role: 'resetZoom' },
                    { role: 'zoomIn' },
                    { role: 'zoomOut' },
                    { type: 'separator' },
                    { role: 'togglefullscreen' }
                ]
            },
            {
                label: 'Help',
                submenu: [
                    {
                        label: 'About Covenantrix',
                        click: () => {
                            dialog.showMessageBox(this.mainWindow, {
                                type: 'info',
                                title: 'About Covenantrix',
                                message: 'Covenantrix Desktop',
                                detail: 'AI-Powered Legal Document Analysis\nVersion 1.0.8'
                            });
                        }
                    },
                    {
                        label: 'API Documentation',
                        click: () => {
                            shell.openExternal(`${this.serviceUrl}/docs`);
                        }
                    }
                ]
            }
        ];

        // macOS specific menu adjustments
        if (process.platform === 'darwin') {
            template.unshift({
                label: app.getName(),
                submenu: [
                    { role: 'about' },
                    { type: 'separator' },
                    { role: 'services' },
                    { type: 'separator' },
                    { role: 'hide' },
                    { role: 'hideOthers' },
                    { role: 'unhide' },
                    { type: 'separator' },
                    { role: 'quit' }
                ]
            });
        }

        const menu = Menu.buildFromTemplate(template);
        Menu.setApplicationMenu(menu);
    }

    setupIpcHandlers() {
        // File dialog for document selection
        ipcMain.handle('select-file', async () => {
            const result = await dialog.showOpenDialog(this.mainWindow, {
                properties: ['openFile'],
                filters: [
                    { name: 'Documents', extensions: ['pdf', 'docx', 'doc', 'txt'] },
                    { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'tiff'] },
                    { name: 'All Files', extensions: ['*'] }
                ]
            });
            
            return result.canceled ? null : result.filePaths[0];
        });

        // API proxy methods
        ipcMain.handle('api-call', async (event, method, endpoint, data) => {
            try {
                const config = {
                    method: method,
                    url: `${this.serviceUrl}${endpoint}`,
                    timeout: 30000 // 30 second timeout
                };

                if (data) {
                    if (method === 'GET') {
                        config.params = data;
                    } else {
                        config.data = data;
                    }
                }

                const response = await axios(config);
                return { success: true, data: response.data };
            } catch (error) {
                console.error('API call failed:', error);
                return { 
                    success: false, 
                    error: error.message,
                    status: error.response?.status
                };
            }
        });

        // File upload handler
        ipcMain.handle('upload-file', async (event, filePath, folderId = 'default') => {
            try {
                const FormData = require('form-data');
                const fs = require('fs');
                
                const form = new FormData();
                form.append('file', fs.createReadStream(filePath));
                form.append('folder_id', folderId);

                const response = await axios.post(
                    `${this.serviceUrl}/api/documents/upload`,
                    form,
                    { 
                        headers: form.getHeaders(),
                        timeout: 60000 // 60 second timeout for uploads
                    }
                );

                return { success: true, data: response.data };
            } catch (error) {
                console.error('File upload failed:', error);
                return { 
                    success: false, 
                    error: error.message 
                };
            }
        });
    }
}

// App instance
const covenantrixApp = new CovenantrixApp();

// App event handlers
app.whenReady().then(async () => {
    await covenantrixApp.createWindow();
    covenantrixApp.createMenu();
    covenantrixApp.setupIpcHandlers();
});

app.on('window-all-closed', () => {
    covenantrixApp.disconnectFromService();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        await covenantrixApp.createWindow();
    }
});

app.on('before-quit', () => {
    covenantrixApp.disconnectFromService();
});

// Handle protocol for deep linking (optional)
app.setAsDefaultProtocolClient('covenantrix');
