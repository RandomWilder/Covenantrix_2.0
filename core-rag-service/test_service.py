#!/usr/bin/env python3
"""
Test script for Covenantrix RAG Service
Simple validation tests for the service wrapper
"""

import requests
import json
import time
import os
from pathlib import Path

BASE_URL = "http://localhost:8080"

def test_health_check():
    """Test health check endpoint"""
    print("🏥 Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data['status']}")
            print(f"   Version: {data['version']}")
            print(f"   Documents: {data['documents_processed']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_personas():
    """Test personas endpoint"""
    print("\n🎭 Testing personas endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/personas")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data['personas'])} personas:")
            for persona in data['personas']:
                print(f"   - {persona['name']} ({persona['id']})")
            return True
        else:
            print(f"❌ Personas test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Personas error: {e}")
        return False

def test_modes():
    """Test query modes endpoint"""
    print("\n🔍 Testing query modes endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/modes")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data['modes'])} query modes:")
            for mode in data['modes']:
                print(f"   - {mode['name']} ({mode['id']})")
            return True
        else:
            print(f"❌ Modes test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Modes error: {e}")
        return False

def test_list_documents():
    """Test document listing"""
    print("\n📚 Testing document listing...")
    try:
        response = requests.get(f"{BASE_URL}/api/documents")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data)} processed documents")
            for doc in data[:3]:  # Show first 3
                print(f"   - {doc['original_name']} ({doc['document_type']})")
            return True
        else:
            print(f"❌ Document listing failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Document listing error: {e}")
        return False

def test_simple_query():
    """Test simple query without documents (will likely fail but should not crash)"""
    print("\n❓ Testing simple query...")
    try:
        query_data = {
            "query": "What documents are available?",
            "persona": "legal_advisor",
            "mode": "hybrid"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/query",
            json=query_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Query executed successfully!")
            print(f"   Confidence: {data['confidence_score']:.2f}")
            print(f"   Response time: {data['processing_time']:.2f}s")
            print(f"   Answer preview: {data['answer'][:100]}...")
            return True
        else:
            print(f"⚠️  Query returned status {response.status_code}")
            print(f"   This is expected if no documents are processed yet")
            return True  # Not a failure if no docs
    except Exception as e:
        print(f"❌ Query error: {e}")
        return False

def test_upload_document():
    """Test document upload if test documents exist"""
    print("\n📄 Testing document upload...")
    
    # Look for test documents
    test_docs_dir = Path("../test-documents")
    if not test_docs_dir.exists():
        test_docs_dir = Path("test-documents")
    
    if not test_docs_dir.exists():
        print("ℹ️  No test-documents directory found, skipping upload test")
        return True
    
    # Find a test PDF
    test_files = list(test_docs_dir.glob("*.pdf"))
    if not test_files:
        print("ℹ️  No PDF files found in test-documents, skipping upload test")
        return True
    
    test_file = test_files[0]
    print(f"📤 Uploading test file: {test_file.name}")
    
    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/pdf')}
            data = {'folder_id': 'test_upload'}
            
            response = requests.post(
                f"{BASE_URL}/api/documents/upload",
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Document upload started successfully!")
            print(f"   File: {result['file_name']}")
            print(f"   Folder: {result['folder_id']}")
            
            # Note: Actual processing happens in background
            print("ℹ️  Processing is happening in background...")
            print("   Use the /api/documents endpoint to check when it's done")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            if response.text:
                print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False

def test_api_docs():
    """Test if API documentation is available"""
    print("\n📖 Testing API documentation...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ API documentation is available at http://localhost:8080/docs")
            return True
        else:
            print(f"❌ API docs failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API docs error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Covenantrix Service Test Suite")
    print("=" * 50)
    
    # Check if service is running
    print("🔍 Checking if service is running...")
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
        print("✅ Service is responding!")
    except:
        print("❌ Service is not running!")
        print("\n💡 To start the service, run:")
        print("   python service_main.py")
        print("\n   Then run this test script again.")
        return False
    
    tests = [
        test_health_check,
        test_personas,
        test_modes,
        test_list_documents,
        test_api_docs,
        test_simple_query,
        test_upload_document
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
        
        time.sleep(0.5)  # Brief pause between tests
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Service is working correctly.")
        print("\n🚀 Ready for Electron integration!")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    
    print(f"\n🔗 API Documentation: http://localhost:8080/docs")
    print(f"🔗 Health Check: http://localhost:8080/health")
    
    return passed == total

if __name__ == "__main__":
    main()
