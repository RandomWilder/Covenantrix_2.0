#!/usr/bin/env python3
"""
Covenantrix RAG Service - Web API Wrapper
Minimal FastAPI service that wraps the existing CLI functionality
"""

# Fix Windows console encoding for Unicode characters (emojis)
import sys
import os
if sys.platform.startswith('win'):
    # Set UTF-8 encoding for Windows console
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Reconfigure stdout/stderr for UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import json
import tempfile
import shutil

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from main import CovenantrixCLI
from query_engine import PersonaType, QueryMode, QueryContext
from settings_manager import SettingsManager

# Pydantic models for API contracts
class QueryRequest(BaseModel):
    query: str
    persona: str = "legal_advisor"
    mode: str = "hybrid"
    conversation_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence_score: float
    query_mode: str
    persona_used: str
    processing_time: float
    conversation_id: str
    timestamp: str

class DocumentInfo(BaseModel):
    id: str
    original_name: str
    document_type: str
    folder_id: str
    file_size: int
    processed_at: str
    processing_time: float
    chunk_count: int
    entities_extracted: int

class ProcessingStatus(BaseModel):
    status: str
    progress: int
    message: str
    document_id: Optional[str] = None

class HealthCheck(BaseModel):
    status: str
    version: str
    timestamp: str
    documents_processed: int

# Settings API models
class ProviderKeyRequest(BaseModel):
    provider: str
    api_key: str

class ProviderKeyResponse(BaseModel):
    success: bool
    message: str
    provider: str

class ValidationRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None

class ValidationResponse(BaseModel):
    valid: bool
    provider: str
    error: Optional[str] = None
    models: Optional[List[str]] = None
    organization: Optional[str] = None
    validated_at: Optional[str] = None

class SettingsResponse(BaseModel):
    providers: Dict[str, Dict[str, Any]]
    preferences: Dict[str, Any]
    created_at: str
    updated_at: str

# Global service instance
service_instance = None
processing_tasks = {}

class CovenantrixService:
    """
    Service wrapper around the existing CLI functionality
    """
    
    def __init__(self):
        self.settings_manager = SettingsManager("./covenantrix_data")
        self.cli = CovenantrixCLI(settings_manager=self.settings_manager)
        self.initialized = False
        self.temp_dir = Path(tempfile.gettempdir()) / "covenantrix_uploads"
        self.temp_dir.mkdir(exist_ok=True)
        
    async def initialize(self):
        """Initialize the RAG system"""
        if not self.initialized:
            print("🚀 Initializing Covenantrix Service...")
            
            # Initialize settings manager first
            await self.settings_manager.initialize()
            print("✅ Settings manager initialized")
            
            await self.cli.initialize()
            self.initialized = True
            print("✅ Service initialized successfully!")
    
    async def process_document(self, file_path: str, folder_id: str = "default") -> Dict:
        """Process a single document"""
        if not self.initialized:
            await self.initialize()
        
        # Progress callback for status updates
        async def progress_callback(status, percentage):
            if file_path in processing_tasks:
                processing_tasks[file_path] = {
                    "status": status,
                    "progress": percentage,
                    "message": f"{status} ({percentage}%)"
                }
        
        try:
            metadata = await self.cli.process_documents([file_path], folder_id)
            if metadata:
                doc_info = metadata[0]
                return {
                    "success": True,
                    "document": {
                        "id": doc_info.id,
                        "original_name": doc_info.original_name,
                        "document_type": doc_info.document_type,
                        "folder_id": doc_info.folder_id,
                        "file_size": doc_info.file_size,
                        "processed_at": doc_info.processed_at.isoformat(),
                        "processing_time": doc_info.processing_time,
                        "chunk_count": doc_info.chunk_count,
                        "entities_extracted": doc_info.entities_extracted
                    }
                }
            else:
                raise Exception("No metadata returned")
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Clean up processing status
            processing_tasks.pop(file_path, None)
    
    async def query_documents(self, query_req: QueryRequest) -> QueryResponse:
        """Execute a query against processed documents"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Build query context
            context = QueryContext(
                persona=PersonaType(query_req.persona),
                mode=QueryMode(query_req.mode)
            )
            
            # Execute query
            response = await self.cli.query_engine.query(
                query_req.query, 
                context, 
                query_req.conversation_id
            )
            
            return QueryResponse(
                answer=response.answer,
                sources=response.sources,
                confidence_score=response.confidence_score,
                query_mode=response.query_mode,
                persona_used=response.persona_used,
                processing_time=response.processing_time,
                conversation_id=response.conversation_id,
                timestamp=response.timestamp.isoformat()
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    
    async def list_documents(self, folder_id: Optional[str] = None) -> List[DocumentInfo]:
        """List processed documents"""
        if not self.initialized:
            await self.initialize()
        
        try:
            documents = await self.cli.doc_processor.list_documents(folder_id)
            return [
                DocumentInfo(
                    id=doc.id,
                    original_name=doc.original_name,
                    document_type=doc.document_type,
                    folder_id=doc.folder_id,
                    file_size=doc.file_size,
                    processed_at=doc.processed_at.isoformat(),
                    processing_time=doc.processing_time,
                    chunk_count=doc.chunk_count,
                    entities_extracted=doc.entities_extracted
                )
                for doc in documents
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")
    
    async def get_analytics(self) -> Dict:
        """Get query analytics"""
        if not self.initialized:
            await self.initialize()
        
        try:
            return await self.cli.query_engine.get_query_analytics()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan event handler"""
    # Startup
    global service_instance
    service_instance = CovenantrixService()
    print("🌟 Covenantrix Service API started!")
    yield
    # Shutdown (add cleanup here if needed)

# FastAPI app setup with lifespan
app = FastAPI(
    title="Covenantrix RAG Service",
    description="AI-powered legal document analysis service",
    version="1.0.5",
    lifespan=lifespan
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    try:
        documents = await service_instance.list_documents() if service_instance.initialized else []
        return HealthCheck(
            status="healthy",
            version="1.0.5",
            timestamp=datetime.now().isoformat(),
            documents_processed=len(documents)
        )
    except:
        return HealthCheck(
            status="starting",
            version="1.0.5", 
            timestamp=datetime.now().isoformat(),
            documents_processed=0
        )

@app.post("/api/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    folder_id: str = "default"
):
    """Upload and process a document"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Save uploaded file temporarily
    temp_file = service_instance.temp_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Initialize processing status
        processing_tasks[str(temp_file)] = {
            "status": "Starting",
            "progress": 0,
            "message": "Document upload completed, processing started..."
        }
        
        # Start background processing
        background_tasks.add_task(service_instance.process_document, str(temp_file), folder_id)
        
        return {
            "message": "Document upload successful, processing started",
            "file_name": file.filename,
            "temp_path": str(temp_file),
            "folder_id": folder_id
        }
        
    except Exception as e:
        # Cleanup on error
        if temp_file.exists():
            temp_file.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/documents/processing/{file_path:path}")
async def get_processing_status(file_path: str):
    """Get document processing status"""
    if file_path in processing_tasks:
        return ProcessingStatus(**processing_tasks[file_path])
    else:
        raise HTTPException(status_code=404, detail="Processing task not found")

@app.get("/api/documents", response_model=List[DocumentInfo])
async def list_documents(folder_id: Optional[str] = None):
    """List processed documents"""
    return await service_instance.list_documents(folder_id)

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document by ID"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    success = await service_instance.cli.doc_processor.delete_document(doc_id)
    if success:
        return {"message": f"Document {doc_id} deleted successfully", "success": True}
    else:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found or could not be deleted")

@app.delete("/api/documents/by-name/{filename}")
async def delete_document_by_name(filename: str):
    """Delete a document by filename"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    success = await service_instance.cli.doc_processor.delete_document_by_name(filename)
    if success:
        return {"message": f"Document '{filename}' deleted successfully", "success": True}
    else:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found or could not be deleted")

@app.delete("/api/documents")
async def clear_all_documents():
    """Clear all documents from the system (nuclear option)"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    cleared_count = await service_instance.cli.doc_processor.clear_all_documents()
    return {
        "message": f"Cleared {cleared_count} documents from the system", 
        "success": True,
        "documents_cleared": cleared_count
    }

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(query_req: QueryRequest):
    """Execute a query against processed documents"""
    return await service_instance.query_documents(query_req)

@app.get("/api/analytics")
async def get_analytics():
    """Get query analytics"""
    return await service_instance.get_analytics()

@app.get("/api/personas")
async def get_personas():
    """Get available personas"""
    return {
        "personas": [
            {
                "id": persona.value,
                "name": persona.value.replace('_', ' ').title(),
                "description": f"Specialized {persona.value.replace('_', ' ')} assistant"
            }
            for persona in PersonaType
        ]
    }

@app.get("/api/modes")
async def get_query_modes():
    """Get available query modes"""
    return {
        "modes": [
            {
                "id": mode.value,
                "name": mode.value.title(),
                "description": f"{mode.value.title()} query mode"
            }
            for mode in QueryMode
        ]
    }

# Settings Management Endpoints

@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    """Get all user settings"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    settings_data = await service_instance.settings_manager.get_all_settings()
    return SettingsResponse(**settings_data)

@app.get("/api/settings/providers")
async def get_providers():
    """Get available providers and their status"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    settings_data = await service_instance.settings_manager.get_all_settings()
    return {"providers": settings_data["providers"]}

@app.put("/api/settings/providers/{provider}/api-key", response_model=ProviderKeyResponse)
async def set_provider_api_key(provider: str, request: ProviderKeyRequest):
    """Set API key for a provider"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    if provider != request.provider:
        raise HTTPException(status_code=400, detail="Provider in URL and body must match")
    
    success = await service_instance.settings_manager.set_api_key(provider, request.api_key)
    
    if success:
        return ProviderKeyResponse(
            success=True,
            message=f"API key for {provider} set successfully",
            provider=provider
        )
    else:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to set API key for {provider}"
        )

@app.delete("/api/settings/providers/{provider}/api-key", response_model=ProviderKeyResponse)
async def delete_provider_api_key(provider: str):
    """Delete API key for a provider"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    success = await service_instance.settings_manager.delete_api_key(provider)
    
    if success:
        return ProviderKeyResponse(
            success=True,
            message=f"API key for {provider} deleted successfully",
            provider=provider
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete API key for {provider}"
        )

@app.post("/api/settings/providers/{provider}/validate", response_model=ValidationResponse)
async def validate_provider_api_key(provider: str, request: Optional[ValidationRequest] = None):
    """Validate API key for a provider"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    # Use provided API key or get from settings
    api_key = None
    if request and request.api_key:
        api_key = request.api_key
    
    validation_result = await service_instance.settings_manager.validate_api_key(provider, api_key)
    
    # Update validation status in settings
    if validation_result.get("valid"):
        await service_instance.settings_manager.update_validation_status(provider, validation_result)
    
    return ValidationResponse(**validation_result)

@app.get("/api/settings/active-provider")
async def get_active_provider():
    """Get currently active provider"""
    if not service_instance.initialized:
        await service_instance.initialize()
    
    active_provider = await service_instance.settings_manager.get_active_provider()
    
    return {
        "active_provider": active_provider,
        "has_active_provider": active_provider is not None
    }

def main():
    """Run the service"""
    print("🚀 Starting Covenantrix RAG Service...")
    print("📖 API documentation will be available at http://localhost:8080/docs")
    
    # Note: API key checking is now handled by the settings manager
    # The service can start without an API key and users can configure it via the settings UI
    print("💡 Configure your OpenAI API key via the settings API: PUT /api/settings/providers/openai/api-key")
    
    uvicorn.run(
        "service_main:app",
        host="127.0.0.1", 
        port=8080,
        log_level="info",
        reload=False  # Set to True for development
    )

if __name__ == "__main__":
    main()
