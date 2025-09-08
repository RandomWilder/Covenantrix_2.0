// preload.js - Security bridge between main and renderer processes
const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
    // File operations
    selectFile: () => ipcRenderer.invoke('select-file'),
    uploadFile: (filePath, folderId) => ipcRenderer.invoke('upload-file', filePath, folderId),
    
    // API calls to Python service
    apiCall: (method, endpoint, data) => ipcRenderer.invoke('api-call', method, endpoint, data),
    
    // Service status
    onServiceReady: (callback) => ipcRenderer.on('service-ready', callback),
    
    // Menu events
    onMenuUploadDocument: (callback) => ipcRenderer.on('menu-upload-document', callback),
    
    // Utility
    removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
    
    // Pre-configured API methods for convenience
    api: {
        // Document management
        listDocuments: (folderId) => 
            ipcRenderer.invoke('api-call', 'GET', '/api/documents', folderId ? { folder_id: folderId } : null),
        
        // Query system
        query: (queryData) => 
            ipcRenderer.invoke('api-call', 'POST', '/api/query', queryData),
        
        // System info
        getHealth: () => 
            ipcRenderer.invoke('api-call', 'GET', '/health'),
        
        getPersonas: () => 
            ipcRenderer.invoke('api-call', 'GET', '/api/personas'),
        
        getModes: () => 
            ipcRenderer.invoke('api-call', 'GET', '/api/modes'),
        
        getAnalytics: () => 
            ipcRenderer.invoke('api-call', 'GET', '/api/analytics')
    }
});
