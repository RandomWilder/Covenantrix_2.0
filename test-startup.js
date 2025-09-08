#!/usr/bin/env node
/**
 * Test script to verify Covenantrix startup workflow
 * Tests both development and production-like scenarios
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const axios = require('axios');

const colors = {
    reset: '\x1b[0m',
    green: '\x1b[32m',
    red: '\x1b[31m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    cyan: '\x1b[36m'
};

function log(color, message) {
    console.log(`${colors[color]}${message}${colors.reset}`);
}

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function testServiceConnection(url = 'http://127.0.0.1:8080', maxAttempts = 10) {
    log('blue', `🔗 Testing connection to ${url}...`);
    
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const response = await axios.get(`${url}/health`, { timeout: 2000 });
            if (response.status === 200) {
                log('green', '✅ Service connection successful!');
                return true;
            }
        } catch (error) {
            if (i < maxAttempts - 1) {
                process.stdout.write('.');
                await sleep(1000);
            }
        }
    }
    
    log('red', '❌ Service connection failed');
    return false;
}

function checkFileExists(filePath, description) {
    const exists = fs.existsSync(filePath);
    if (exists) {
        log('green', `✅ ${description}: ${filePath}`);
    } else {
        log('yellow', `⚠️  ${description} not found: ${filePath}`);
    }
    return exists;
}

async function startPythonService(useVenv = false) {
    log('blue', `🚀 Starting Python service ${useVenv ? '(venv)' : '(bundled)'}...`);
    
    let pythonPath, args;
    const projectRoot = process.cwd();
    
    if (useVenv) {
        // Use venv approach
        const venvBinDir = process.platform === 'win32' ? 'Scripts' : 'bin';
        const venvPythonExe = process.platform === 'win32' ? 'python.exe' : 'python';
        pythonPath = path.join(projectRoot, 'venv', venvBinDir, venvPythonExe);
        args = [path.join(projectRoot, 'core-rag-service', 'service_main.py')];
        
        if (!checkFileExists(pythonPath, 'Venv Python')) {
            return null;
        }
    } else {
        // Use bundled executable
        const executableName = process.platform === 'win32' ? 'covenantrix-service.exe' : 'covenantrix-service';
        pythonPath = path.join(projectRoot, 'python-dist', executableName);
        args = [];
        
        if (!checkFileExists(pythonPath, 'Bundled executable')) {
            return null;
        }
    }
    
    try {
        const pythonProcess = spawn(pythonPath, args, {
            cwd: useVenv ? path.join(projectRoot, 'core-rag-service') : path.dirname(pythonPath),
            stdio: ['ignore', 'pipe', 'pipe']
        });
        
        pythonProcess.stdout.on('data', (data) => {
            process.stdout.write(`[Python] ${data}`);
        });
        
        pythonProcess.stderr.on('data', (data) => {
            process.stderr.write(`[Python Error] ${data}`);
        });
        
        // Wait a moment for service to start
        await sleep(3000);
        
        return pythonProcess;
    } catch (error) {
        log('red', `❌ Failed to start Python service: ${error.message}`);
        return null;
    }
}

async function runTests() {
    log('cyan', '🧪 Starting Covenantrix Startup Tests');
    log('cyan', '=====================================');
    
    console.log();
    log('blue', '📋 Phase 1: Environment Check');
    log('blue', '-----------------------------');
    
    // Check project structure
    const checks = [
        { path: 'package.json', desc: 'Package configuration' },
        { path: 'electron-app/src/main.js', desc: 'Electron main process' },
        { path: 'core-rag-service/service_main.py', desc: 'Python service' },
        { path: 'core-rag-service/config.yaml', desc: 'Service configuration' },
        { path: 'covenantrix-service.spec', desc: 'PyInstaller spec' },
        { path: 'venv', desc: 'Python virtual environment' }
    ];
    
    const envOk = checks.every(check => checkFileExists(check.path, check.desc));
    
    console.log();
    log('blue', '📋 Phase 2: Bundled Executable Test');
    log('blue', '-----------------------------------');
    
    let bundledProcess = null;
    let bundledWorking = false;
    
    if (checkFileExists('python-dist', 'Python dist directory')) {
        bundledProcess = await startPythonService(false);
        if (bundledProcess) {
            bundledWorking = await testServiceConnection();
        }
    } else {
        log('yellow', '⚠️  Bundled executable not found, skipping test');
    }
    
    // Clean up bundled process
    if (bundledProcess) {
        bundledProcess.kill();
        await sleep(2000);
    }
    
    console.log();
    log('blue', '📋 Phase 3: Venv Fallback Test');
    log('blue', '------------------------------');
    
    let venvProcess = null;
    let venvWorking = false;
    
    if (checkFileExists('venv', 'Virtual environment')) {
        venvProcess = await startPythonService(true);
        if (venvProcess) {
            venvWorking = await testServiceConnection();
        }
    } else {
        log('yellow', '⚠️  Virtual environment not found, skipping test');
    }
    
    // Clean up venv process
    if (venvProcess) {
        venvProcess.kill();
        await sleep(2000);
    }
    
    console.log();
    log('cyan', '📊 Test Results Summary');
    log('cyan', '======================');
    
    log(envOk ? 'green' : 'red', `Environment Setup: ${envOk ? '✅ PASS' : '❌ FAIL'}`);
    log(bundledWorking ? 'green' : 'yellow', `Bundled Executable: ${bundledWorking ? '✅ PASS' : '⚠️  SKIP'}`);
    log(venvWorking ? 'green' : 'red', `Venv Fallback: ${venvWorking ? '✅ PASS' : '❌ FAIL'}`);
    
    console.log();
    if (bundledWorking || venvWorking) {
        log('green', '🎉 Startup system is working! You can now run:');
        log('green', '   npm start  (or npm run dev)');
    } else {
        log('red', '❌ Startup system needs attention:');
        if (!venvWorking) {
            log('red', '   1. Run "npm run setup-dev" to set up development environment');
        }
        if (!bundledWorking && fs.existsSync('venv')) {
            log('yellow', '   2. Bundled executable missing (normal for development)');
        }
    }
    
    console.log();
    log('blue', '💡 Development Tips:');
    log('blue', '   - Run "npm run setup-dev" for full development setup');
    log('blue', '   - Run "npm start" for automatic service startup');
    log('blue', '   - Check DEV-SETUP.md for detailed instructions');
}

if (require.main === module) {
    runTests().catch(error => {
        log('red', `❌ Test failed: ${error.message}`);
        process.exit(1);
    });
}

module.exports = { runTests, testServiceConnection };
