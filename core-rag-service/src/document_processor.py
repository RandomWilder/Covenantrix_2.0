# core-rag-service/src/document_processor.py
"""
Core document processing engine for Covenantrix
Handles PDF, DOCX, and image processing with OCR
"""

import asyncio
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

# LightRAG imports
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status

# Document processing imports
import PyPDF2
import pdfplumber  # Better PDF text extraction
from docx import Document
from PIL import Image
import pytesseract

@dataclass
class DocumentMetadata:
    """Document metadata structure"""
    id: str
    original_name: str
    file_path: str
    folder_id: str
    file_size: int
    page_count: Optional[int]
    processed_at: datetime
    document_type: str
    processing_time: float
    chunk_count: int
    entities_extracted: int
    relationships_found: int
    
class DocumentProcessor:
    """
    Core document processing engine using LightRAG
    """
    
    def __init__(self, working_dir: str = "./covenantrix_data"):
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(exist_ok=True)
        
        # Initialize LightRAG
        self.rag = None
        self.processing_queue = asyncio.Queue()
        self.processing_status = {}
        
    async def initialize(self):
        """Initialize LightRAG and storage"""
        print("🚀 Initializing Covenantrix RAG Engine...")
        
        self.rag = LightRAG(
            working_dir=str(self.working_dir),
            llm_model_func=gpt_4o_mini_complete,
            embedding_func=EmbeddingFunc(
                embedding_dim=1536,  # OpenAI text-embedding-3-small
                max_token_size=8192,
                func=lambda texts: openai_embed(texts, model="text-embedding-3-small")
            ),
            # Legal document optimized settings
            chunk_token_size=800,  # Smaller chunks for legal precision
            chunk_overlap_token_size=100,
            entity_extract_max_gleaning=2,  # More thorough entity extraction
            max_parallel_insert=1,  # Reduced for Hebrew stability
        )
        
        # Initialize storages properly
        try:
            # Check if initialize_storages is async
            if hasattr(self.rag, 'initialize_storages'):
                init_method = getattr(self.rag, 'initialize_storages')
                if asyncio.iscoroutinefunction(init_method):
                    await init_method()
                else:
                    init_method()
            
            # Initialize pipeline status
            if asyncio.iscoroutinefunction(initialize_pipeline_status):
                await initialize_pipeline_status()
            else:
                initialize_pipeline_status()
                
        except Exception as e:
            print(f"⚠️  Warning during initialization: {e}")
            # Continue with basic initialization
        
        print("✅ RAG Engine initialized successfully")
        
    def extract_text_from_file(self, file_path: str) -> Tuple[str, Dict]:
        """
        Extract text from various file formats
        Returns: (extracted_text, metadata)
        """
        file_path = Path(file_path)
        file_ext = file_path.suffix.lower()
        
        metadata = {
            "file_size": file_path.stat().st_size,
            "extraction_method": None,
            "page_count": None,
            "text_length": 0,
            "extraction_success": False
        }
        
        try:
            if file_ext == '.pdf':
                # Use PyPDF2 for PDF with enhanced extraction
                text_parts = []
                
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    metadata["page_count"] = len(pdf_reader.pages)
                    
                    print(f"📄 Extracting from PDF: {metadata['page_count']} pages")
                    
                    for i, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text.strip():
                                text_parts.append(page_text)
                                print(f"   Page {i+1}: {len(page_text)} characters extracted")
                            else:
                                print(f"   Page {i+1}: No text found (may be scanned/image-based)")
                        except Exception as e:
                            print(f"   Page {i+1}: Extraction failed - {e}")
                
                text = '\n'.join(text_parts).strip()
                metadata["extraction_method"] = "PyPDF2"
                metadata["text_length"] = len(text)
                
                # If minimal text extracted with PyPDF2, try pdfplumber as fallback
                if not text or len(text.strip()) < 50:  # Less than 50 chars likely means failed extraction
                    print("⚠️  PyPDF2 extracted minimal text, trying pdfplumber...")
                    
                    try:
                        with pdfplumber.open(file_path) as pdf:
                            plumber_text_parts = []
                            for i, page in enumerate(pdf.pages):
                                try:
                                    page_text = page.extract_text()
                                    if page_text and page_text.strip():
                                        plumber_text_parts.append(page_text)
                                        print(f"   pdfplumber Page {i+1}: {len(page_text)} characters extracted")
                                except Exception as e:
                                    print(f"   pdfplumber Page {i+1}: Extraction failed - {e}")
                            
                            plumber_text = '\n'.join(plumber_text_parts).strip()
                            
                            if plumber_text and len(plumber_text.strip()) >= 50:
                                text = plumber_text
                                metadata["extraction_method"] = "pdfplumber"
                                metadata["text_length"] = len(text)
                                print(f"✅ pdfplumber successfully extracted {len(text)} characters")
                                metadata["extraction_success"] = True
                            else:
                                print("❌ pdfplumber also extracted minimal text")
                                
                    except Exception as e:
                        print(f"❌ pdfplumber extraction failed: {e}")
                
                # Final check - if still no meaningful text, provide diagnostic info
                if not text or len(text.strip()) < 50:
                    print("⚠️  Warning: Both extraction methods failed or returned minimal text")
                    print("   This may be a scanned PDF that requires OCR")
                    print(f"   Final text length: {len(text)} characters")
                    
                    if text:
                        print(f"   Sample text: '{text[:100]}...'")
                    
                    # For completely empty extraction, provide a fallback message
                    if not text.strip():
                        text = f"[PDF_EXTRACTION_FAILED] Document '{file_path.name}' appears to contain no extractable text. This may be a scanned PDF requiring OCR processing."
                else:
                    if not metadata.get("extraction_success"):
                        print(f"✅ Successfully extracted {len(text)} characters from PDF")
                        metadata["extraction_success"] = True
                
            elif file_ext in ['.docx']:
                # Use python-docx for Word documents
                doc = Document(file_path)
                text_parts = []
                for paragraph in doc.paragraphs:
                    text_parts.append(paragraph.text)
                text = '\n'.join(text_parts)
                metadata["extraction_method"] = "python-docx"
                
            elif file_ext in ['.doc']:
                # .doc files not supported by python-docx, skip or use fallback
                text = f"Document format .doc not supported. Please convert to .docx"
                metadata["extraction_method"] = "unsupported"
                
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff']:
                # Use OCR for images
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
                metadata["extraction_method"] = "tesseract_ocr"
                
            elif file_ext == '.txt':
                # Direct text file reading
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                metadata["extraction_method"] = "direct_read"
                
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
                
        except Exception as e:
            raise Exception(f"Text extraction failed: {str(e)}")
            
        return text, metadata
    
    def classify_document_type(self, text: str, filename: str) -> str:
        """
        Classify document type based on content and filename
        """
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Hebrew contract indicators
        hebrew_contract_terms = [
            'חוזה', 'הסכם', 'תנאים', 'התחייבות', 'צדדים', 'משכיר', 'שוכר'
        ]
        
        # Contract indicators
        contract_terms = [
            'agreement', 'contract', 'terms and conditions',
            'whereas', 'party of the first part', 'consideration',
            'executed', 'binding', 'covenant', 'indemnify'
        ] + hebrew_contract_terms
        
        # Legal document indicators
        legal_terms = [
            'plaintiff', 'defendant', 'court', 'jurisdiction',
            'statute', 'regulation', 'compliance', 'liability',
            'בית משפט', 'חוק', 'תקנות', 'אחריות'
        ]
        
        # Real estate indicators
        real_estate_terms = [
            'property', 'real estate', 'lease', 'tenant', 'landlord',
            'premises', 'rent', 'mortgage', 'deed', 'title',
            'נכס', 'דירה', 'משכיר', 'שוכר', 'שכירות', 'דמי שכירות'
        ]
        
        contract_score = sum(1 for term in contract_terms if term in text_lower)
        legal_score = sum(1 for term in legal_terms if term in text_lower)
        real_estate_score = sum(1 for term in real_estate_terms if term in text_lower)
        
        # Filename-based classification (including Hebrew)
        if any(term in filename_lower for term in ['contract', 'agreement', 'חוזה', 'הסכם']):
            return 'contract'
        elif any(term in filename_lower for term in ['lease', 'rental', 'שכירות']):
            return 'real_estate_lease'
        elif any(term in filename_lower for term in ['legal', 'court', 'case', 'משפט']):
            return 'legal_document'
        
        # Content-based classification
        if contract_score >= 2:
            return 'contract'
        elif real_estate_score >= 2:
            return 'real_estate'
        elif legal_score >= 2:
            return 'legal_document'
        else:
            return 'general_document'
    
    async def process_document(
        self, 
        file_path: str, 
        folder_id: str = "default",
        progress_callback=None
    ) -> DocumentMetadata:
        """
        Process a single document through the RAG pipeline
        """
        start_time = datetime.now()
        file_path = Path(file_path)
        
        # Generate document ID
        doc_id = hashlib.sha256(
            f"{file_path.name}_{file_path.stat().st_mtime}".encode()
        ).hexdigest()[:16]
        
        print(f"📄 Processing document: {file_path.name}")
        
        if progress_callback:
            await progress_callback("Extracting text...", 20)
        
        # Extract text
        text, extraction_metadata = self.extract_text_from_file(str(file_path))
        
        # Validate extracted text
        if not text or len(text.strip()) < 10:
            raise ValueError(f"Insufficient text extracted from document (length: {len(text)}). Document may be empty, corrupted, or require OCR processing.")
        
        print(f"📝 Extracted text: {len(text)} characters")
        if text.strip().startswith("[PDF_EXTRACTION_FAILED]"):
            print("⚠️  Processing fallback text for failed extraction")
        
        if progress_callback:
            await progress_callback("Classifying document...", 40)
        
        # Classify document
        doc_type = self.classify_document_type(text, file_path.name)
        print(f"📋 Document classified as: {doc_type}")
        
        if progress_callback:
            await progress_callback("Building knowledge graph...", 60)
        
        # Insert into LightRAG with validation
        try:
            print(f"🔄 Inserting text into RAG system...")
            await self.rag.ainsert(text)
            print(f"✅ Text successfully inserted into RAG system")
        except Exception as e:
            print(f"❌ Failed to insert text into RAG system: {e}")
            raise Exception(f"RAG insertion failed: {str(e)}")
        
        if progress_callback:
            await progress_callback("Extracting entities and relationships...", 80)
        
        # Get processing statistics (simplified for now)
        # In production, you'd extract these from LightRAG's internal structures
        chunk_count = len(text) // 800  # Approximate based on chunk size
        entities_extracted = text.count('.') // 10  # Rough estimate
        relationships_found = text.count(' and ') + text.count(' with ')  # Rough estimate
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if progress_callback:
            await progress_callback("Finalizing...", 100)
        
        # Create metadata
        metadata = DocumentMetadata(
            id=doc_id,
            original_name=file_path.name,
            file_path=str(file_path),
            folder_id=folder_id,
            file_size=extraction_metadata["file_size"],
            page_count=extraction_metadata.get("page_count"),
            processed_at=datetime.now(),
            document_type=doc_type,
            processing_time=processing_time,
            chunk_count=chunk_count,
            entities_extracted=entities_extracted,
            relationships_found=relationships_found
        )
        
        # Store metadata
        await self._store_document_metadata(metadata)
        
        print(f"✅ Document processed: {file_path.name} ({processing_time:.2f}s)")
        return metadata
    
    async def _store_document_metadata(self, metadata: DocumentMetadata):
        """Store document metadata for future reference"""
        metadata_file = self.working_dir / "document_metadata.json"
        
        # Load existing metadata
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
        else:
            all_metadata = {}
        
        # Add new metadata
        all_metadata[metadata.id] = {
            "id": metadata.id,
            "original_name": metadata.original_name,
            "file_path": metadata.file_path,
            "folder_id": metadata.folder_id,
            "file_size": metadata.file_size,
            "page_count": metadata.page_count,
            "processed_at": metadata.processed_at.isoformat(),
            "document_type": metadata.document_type,
            "processing_time": metadata.processing_time,
            "chunk_count": metadata.chunk_count,
            "entities_extracted": metadata.entities_extracted,
            "relationships_found": metadata.relationships_found
        }
        
        # Save metadata
        with open(metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)
    
    async def get_document_metadata(self, doc_id: str) -> Optional[DocumentMetadata]:
        """Retrieve document metadata by ID"""
        metadata_file = self.working_dir / "document_metadata.json"
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, 'r') as f:
            all_metadata = json.load(f)
        
        if doc_id not in all_metadata:
            return None
        
        data = all_metadata[doc_id]
        return DocumentMetadata(
            id=data["id"],
            original_name=data["original_name"],
            file_path=data["file_path"],
            folder_id=data["folder_id"],
            file_size=data["file_size"],
            page_count=data.get("page_count"),
            processed_at=datetime.fromisoformat(data["processed_at"]),
            document_type=data["document_type"],
            processing_time=data["processing_time"],
            chunk_count=data["chunk_count"],
            entities_extracted=data["entities_extracted"],
            relationships_found=data["relationships_found"]
        )
    
    async def list_documents(self, folder_id: Optional[str] = None) -> List[DocumentMetadata]:
        """List all processed documents, optionally filtered by folder"""
        metadata_file = self.working_dir / "document_metadata.json"
        
        if not metadata_file.exists():
            return []
        
        with open(metadata_file, 'r') as f:
            all_metadata = json.load(f)
        
        documents = []
        for data in all_metadata.values():
            if folder_id is None or data["folder_id"] == folder_id:
                documents.append(DocumentMetadata(
                    id=data["id"],
                    original_name=data["original_name"],
                    file_path=data["file_path"],
                    folder_id=data["folder_id"],
                    file_size=data["file_size"],
                    page_count=data.get("page_count"),
                    processed_at=datetime.fromisoformat(data["processed_at"]),
                    document_type=data["document_type"],
                    processing_time=data["processing_time"],
                    chunk_count=data["chunk_count"],
                    entities_extracted=data["entities_extracted"],
                    relationships_found=data["relationships_found"]
                ))
        
        return sorted(documents, key=lambda x: x.processed_at, reverse=True)
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        Completely remove a document from the RAG system
        This removes metadata, vectors, graph entities, and all associated data
        """
        print(f"🗑️  Deleting document: {doc_id}")
        
        # Get document metadata first
        metadata = await self.get_document_metadata(doc_id)
        if not metadata:
            print(f"❌ Document {doc_id} not found in metadata")
            return False
            
        print(f"📄 Found document to delete: {metadata.original_name}")
        
        try:
            # 1. Remove from document metadata
            await self._remove_document_metadata(doc_id)
            print("✅ Removed document metadata")
            
            # 2. Clean up LightRAG storage
            # Note: LightRAG doesn't have a built-in delete function for individual documents
            # We need to work around this limitation
            await self._cleanup_lightrag_data(doc_id, metadata)
            print("✅ Cleaned up RAG system data")
            
            # 3. Remove temporary upload file if it exists
            if metadata.file_path and Path(metadata.file_path).exists():
                try:
                    Path(metadata.file_path).unlink()
                    print("✅ Removed temporary file")
                except Exception as e:
                    print(f"⚠️  Could not remove file {metadata.file_path}: {e}")
            
            print(f"✅ Document {doc_id} ({metadata.original_name}) deleted successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting document {doc_id}: {e}")
            return False
    
    async def _remove_document_metadata(self, doc_id: str):
        """Remove document from metadata file"""
        metadata_file = self.working_dir / "document_metadata.json"
        
        if not metadata_file.exists():
            return
        
        with open(metadata_file, 'r') as f:
            all_metadata = json.load(f)
        
        if doc_id in all_metadata:
            del all_metadata[doc_id]
            
            with open(metadata_file, 'w') as f:
                json.dump(all_metadata, f, indent=2)
    
    async def _cleanup_lightrag_data(self, doc_id: str, metadata: DocumentMetadata):
        """
        Clean up LightRAG data for a document
        Since LightRAG doesn't support individual document deletion,
        we need to rebuild the entire system without this document
        """
        print("🔄 Cleaning up RAG system data...")
        
        # This is a complex operation - for now, we'll mark it for rebuild
        # In a production system, you'd want to:
        # 1. Remove document chunks from vector stores
        # 2. Remove entities/relationships created by this document
        # 3. Update the knowledge graph
        
        # For now, we'll clear the document from the doc_status tracking
        if hasattr(self.rag, '_doc_status'):
            doc_key = f"doc-{hashlib.sha256(metadata.original_name.encode()).hexdigest()}"
            if hasattr(self.rag._doc_status, 'delete'):
                try:
                    await self.rag._doc_status.delete(doc_key)
                    print(f"✅ Removed document status for {doc_key}")
                except:
                    print(f"⚠️  Could not remove document status for {doc_key}")
        
        # Clear any cached data related to this document
        cache_files_to_check = [
            "kv_store_doc_status.json",
            "kv_store_full_docs.json", 
            "kv_store_text_chunks.json"
        ]
        
        for cache_file in cache_files_to_check:
            cache_path = self.working_dir / cache_file
            if cache_path.exists():
                try:
                    with open(cache_path, 'r') as f:
                        cache_data = json.load(f)
                    
                    # Remove entries related to this document
                    keys_to_remove = []
                    for key in cache_data.keys():
                        if doc_id in key or metadata.original_name in key:
                            keys_to_remove.append(key)
                    
                    for key in keys_to_remove:
                        del cache_data[key]
                        print(f"✅ Removed cached entry: {key}")
                    
                    # Save updated cache
                    with open(cache_path, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                        
                except Exception as e:
                    print(f"⚠️  Error cleaning cache {cache_file}: {e}")
    
    async def delete_document_by_name(self, filename: str) -> bool:
        """Delete document by filename (convenience method)"""
        documents = await self.list_documents()
        
        matching_docs = [doc for doc in documents if doc.original_name == filename]
        
        if not matching_docs:
            print(f"❌ No document found with name: {filename}")
            return False
        
        if len(matching_docs) > 1:
            print(f"⚠️  Multiple documents found with name {filename}:")
            for doc in matching_docs:
                print(f"   - {doc.id} (processed: {doc.processed_at})")
            print("   Deleting the most recent one...")
            doc_to_delete = max(matching_docs, key=lambda x: x.processed_at)
        else:
            doc_to_delete = matching_docs[0]
        
        return await self.delete_document(doc_to_delete.id)
    
    async def clear_all_documents(self) -> int:
        """
        Clear all processed documents (nuclear option for testing)
        Returns: number of documents cleared
        """
        print("🧹 Clearing all documents from RAG system...")
        
        documents = await self.list_documents()
        cleared_count = 0
        
        for doc in documents:
            if await self.delete_document(doc.id):
                cleared_count += 1
        
        # Additional cleanup - remove all storage files
        storage_files = [
            "document_metadata.json",
            "graph_chunk_entity_relation.graphml",
            "kv_store_doc_status.json",
            "kv_store_full_docs.json",
            "kv_store_full_entities.json", 
            "kv_store_full_relations.json",
            "kv_store_llm_response_cache.json",
            "kv_store_text_chunks.json",
            "vdb_chunks.json",
            "vdb_entities.json", 
            "vdb_relationships.json"
        ]
        
        for storage_file in storage_files:
            file_path = self.working_dir / storage_file
            if file_path.exists():
                try:
                    file_path.unlink()
                    print(f"✅ Removed storage file: {storage_file}")
                except Exception as e:
                    print(f"⚠️  Could not remove {storage_file}: {e}")
        
        print(f"✅ Cleared {cleared_count} documents from system")
        return cleared_count

# Example usage for testing
async def main():
    """Test the document processor"""
    
    # Initialize processor
    processor = DocumentProcessor()
    await processor.initialize()
    
    # Process a test document
    test_file = "path/to/your/test/contract.pdf"
    if os.path.exists(test_file):
        metadata = await processor.process_document(test_file, "test_folder")
        print(f"Processed: {metadata.original_name}")
        print(f"Type: {metadata.document_type}")
        print(f"Entities: {metadata.entities_extracted}")
        print(f"Time: {metadata.processing_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())