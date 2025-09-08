# PyInstaller spec file for Covenantrix RAG Service
# This creates a standalone executable that bundles Python + all dependencies

import sys
import os
from pathlib import Path

# Get the service directory
service_dir = os.path.join(os.getcwd(), 'core-rag-service')
src_dir = os.path.join(service_dir, 'src')

block_cipher = None

a = Analysis(
    [os.path.join(service_dir, 'service_main.py')],
    pathex=[service_dir, src_dir],
    binaries=[],
    datas=[
        # Include config files
        (os.path.join(service_dir, 'config.yaml'), '.'),
        # Include src directory Python files
        (src_dir, 'src'),
        # Include additional data files that might be needed
        # Note: These will be included if they exist, ignored if not
    ],
    hiddenimports=[
        # Core web framework dependencies
        'uvicorn',
        'uvicorn.main',
        'uvicorn.server',
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'pydantic',
        'pydantic.main',
        'pydantic.fields',
        
        # LightRAG and AI dependencies
        'lightrag',
        'lightrag.llm',
        'lightrag.llm.openai',
        'lightrag.utils',
        'lightrag.kg',
        'lightrag.kg.shared_storage',
        'openai',
        'tiktoken',
        'tiktoken.load',
        'tiktoken.core',
        
        # Document processing dependencies
        'PyPDF2',
        'pdfplumber',
        'docx',
        'docx.document',
        'PIL',
        'PIL.Image',
        'pytesseract',
        
        # Data processing dependencies
        'numpy',
        'pandas',
        'networkx',
        'json',
        'yaml',
        'httpx',
        'nltk',
        
        # System and async dependencies
        'asyncio',
        'multiprocessing',
        'concurrent.futures',
        'pathlib',
        'tempfile',
        'shutil',
        'datetime',
        'hashlib',
        'dataclasses',
        
        # Additional FastAPI dependencies
        'starlette',
        'starlette.applications',
        'starlette.middleware',
        'starlette.responses',
        'starlette.routing',
        
        # Ensure all src module imports
        'main',
        'document_processor',
        'query_engine',
        'settings_manager',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'matplotlib',
        'jupyter',
        'IPython',
        'notebook',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='covenantrix-service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('electron-app', 'assets', 'icon.ico') if sys.platform.startswith('win') else None,
)
