#!/usr/bin/env python3
"""
Test script for document deletion functionality
Run this to clean up documents before reprocessing
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from main import CovenantrixCLI

async def main():
    """Test document deletion"""
    
    print("🧪 Testing Document Deletion Functionality")
    print("=" * 50)
    
    # Initialize the CLI
    cli = CovenantrixCLI()
    await cli.initialize()
    
    # List all documents
    print("\n📋 Current documents in system:")
    documents = await cli.doc_processor.list_documents()
    
    if not documents:
        print("   No documents found")
        return
    
    for i, doc in enumerate(documents, 1):
        print(f"   {i}. {doc.original_name} (ID: {doc.id})")
        print(f"      Type: {doc.document_type}, Processed: {doc.processed_at}")
        print(f"      Entities: {doc.entities_extracted}, Size: {doc.file_size} bytes")
    
    # Ask user what to do
    print(f"\n🤔 What would you like to do?")
    print("   1. Delete a specific document by name")
    print("   2. Clear ALL documents (nuclear option)")
    print("   3. Exit without changes")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        # Delete specific document
        filename = input("\nEnter the filename to delete: ").strip()
        if filename:
            print(f"\n🗑️  Deleting document: {filename}")
            success = await cli.doc_processor.delete_document_by_name(filename)
            if success:
                print("✅ Document deleted successfully!")
            else:
                print("❌ Failed to delete document")
        else:
            print("❌ No filename provided")
    
    elif choice == "2":
        # Clear all documents
        confirm = input("\n⚠️  This will DELETE ALL DOCUMENTS! Are you sure? (yes/no): ").strip().lower()
        if confirm == "yes":
            print("\n🧹 Clearing all documents...")
            cleared_count = await cli.doc_processor.clear_all_documents()
            print(f"✅ Cleared {cleared_count} documents")
        else:
            print("❌ Operation cancelled")
    
    elif choice == "3":
        print("👋 Exiting without changes")
    
    else:
        print("❌ Invalid choice")
    
    # Show final state
    print("\n📋 Documents remaining in system:")
    final_documents = await cli.doc_processor.list_documents()
    if final_documents:
        for doc in final_documents:
            print(f"   - {doc.original_name} (ID: {doc.id})")
    else:
        print("   No documents remaining")

if __name__ == "__main__":
    asyncio.run(main())
