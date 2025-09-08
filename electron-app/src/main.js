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

        // Load the app from build directory (Electron standard)
        this.mainWindow.loadFile(path.join(__dirname, '../build/index.html'));
        
        if (isDev) {
            this.mainWindow.webContents.openDevTools();
        }

        // Show window when ready
        this.mainWindow.once('ready-to-show', () => {
            this.mainWindow.show();
            
            // Connect to existing Python service
            this.connectToExistingService();
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
                    return;
                }
            } catch (error) {
                // Service not responding yet, wait and retry
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        console.error('❌ Could not connect to Python service');
        await this.showServiceConnectionOptions();
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
        console.log('🚀 Starting Python service automatically...');
        const { spawn } = require('child_process');
        const path = require('path');
        
        try {
            // Construct path to Python service
            const projectRoot = path.join(__dirname, '../../');
            const venvPython = path.join(projectRoot, 'venv', 'Scripts', 'python.exe');
            const serviceScript = path.join(projectRoot, 'core-rag-service', 'service_main.py');
            
            // Start the Python service
            this.pythonProcess = spawn(venvPython, [serviceScript], {
                cwd: path.join(projectRoot, 'core-rag-service'),
                stdio: ['ignore', 'pipe', 'pipe']
            });
            
            this.pythonProcess.stdout.on('data', (data) => {
                console.log(`Python Service: ${data}`);
            });
            
            this.pythonProcess.stderr.on('data', (data) => {
                console.error(`Python Service Error: ${data}`);
            });
            
            // Wait for service to start, then connect
            setTimeout(() => {
                this.connectToExistingService(15);
            }, 3000);
            
        } catch (error) {
            console.error('Failed to start Python service:', error);
            this.showServiceError();
        }
    }

    showServiceError() {
        dialog.showErrorBox(
            'Service Connection Error',
            'Cannot connect to the Covenantrix Python service at 127.0.0.1:8080.\n\nPlease make sure the service is running:\n\n1. Open terminal\n2. cd covenantrix-v2\n3. venv\\Scripts\\activate\n4. cd core-rag-service\n5. python service_main.py\n\nThe service should show "Uvicorn running on http://127.0.0.1:8080"'
        );
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
                                detail: 'AI-Powered Legal Document Analysis\nVersion 1.0.0'
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
