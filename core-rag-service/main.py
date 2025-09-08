# core-rag-service/main.py
"""
Main entry point for Covenantrix RAG Service
Provides both CLI testing interface and FastAPI server
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
import argparse
from pathlib import Path
from typing import List, Optional
import json
from datetime import datetime

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from document_processor import DocumentProcessor, DocumentMetadata
from query_engine import (
    QueryEngine, QueryContext, QueryResponse, PersonaType, QueryMode, QueryBuilder
)

class CovenantrixCLI:
    """
    Command-line interface for testing Covenantrix RAG capabilities
    """
    
    def __init__(self, settings_manager=None):
        self.doc_processor = None
        self.query_engine = None
        self.settings_manager = settings_manager
        self.initialized = False
    
    async def initialize(self):
        """Initialize the RAG system"""
        if self.initialized:
            return
        
        print("🚀 Initializing Covenantrix RAG System...")
        print("⏳ This may take a few moments on first run...")
        
        # Check for OpenAI API key from settings or environment
        openai_api_key = None
        
        if self.settings_manager:
            try:
                openai_api_key = await self.settings_manager.get_api_key("openai")
            except Exception as e:
                print(f"⚠️  Warning: Could not load API key from settings: {e}")
        
        # Fallback to environment variable
        if not openai_api_key:
            openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not openai_api_key:
            print("❌ ERROR: OpenAI API key not found")
            print("Please either:")
            print("  1. Set via settings API: PUT /api/settings/providers/openai/api-key")
            print("  2. Set environment variable: export OPENAI_API_KEY='your_key_here'")
            sys.exit(1)
        
        # Set the API key in environment for LightRAG compatibility
        os.environ['OPENAI_API_KEY'] = openai_api_key
        print("✅ OpenAI API key loaded successfully")
        
        try:
            # Initialize document processor
            self.doc_processor = DocumentProcessor("./covenantrix_data")
            await self.doc_processor.initialize()
            
            # Initialize query engine
            self.query_engine = QueryEngine(self.doc_processor)
            
            self.initialized = True
            print("✅ Covenantrix RAG System initialized successfully!")
            
        except Exception as e:
            print(f"❌ Initialization failed: {str(e)}")
            sys.exit(1)
    
    async def process_documents(self, file_paths: List[str], folder_id: str = "default"):
        """Process multiple documents"""
        if not self.initialized:
            await self.initialize()
        
        results = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                continue
            
            print(f"\n📄 Processing: {file_path}")
            
            try:
                # Simple progress callback
                async def progress_callback(status, percentage):
                    print(f"   {status} ({percentage}%)")
                
                metadata = await self.doc_processor.process_document(
                    file_path, folder_id, progress_callback
                )
                
                results.append(metadata)
                
                print(f"✅ Successfully processed: {metadata.original_name}")
                print(f"   📊 Type: {metadata.document_type}")
                print(f"   🔗 Entities: {metadata.entities_extracted}")
                print(f"   ⏱️  Time: {metadata.processing_time:.2f}s")
                
            except Exception as e:
                print(f"❌ Failed to process {file_path}: {str(e)}")
        
        return results
    
    async def interactive_query(self):
        """Start interactive query session"""
        if not self.initialized:
            await self.initialize()
        
        print("\n🤖 Welcome to Covenantrix Interactive Query Session!")
        print("💡 Available personas: legal_advisor, contract_analyst, risk_assessor, legal_writer, compliance_officer")
        print("💡 Available modes: local, global, hybrid, naive, mix")
        print("💡 Type 'help' for commands, 'quit' to exit")
        
        current_persona = PersonaType.LEGAL_ADVISOR
        current_mode = QueryMode.HYBRID
        conversation_id = None
        
        while True:
            try:
                user_input = input(f"\n[{current_persona.value}|{current_mode.value}] Query: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if user_input.startswith('/persona '):
                    persona_name = user_input.split(' ', 1)[1].strip()
                    try:
                        current_persona = PersonaType(persona_name)
                        conversation_id = None  # Reset conversation for new persona
                        print(f"🎭 Switched to persona: {current_persona.value}")
                    except ValueError:
                        print(f"❌ Invalid persona: {persona_name}")
                    continue
                
                if user_input.startswith('/mode '):
                    mode_name = user_input.split(' ', 1)[1].strip()
                    try:
                        current_mode = QueryMode(mode_name)
                        print(f"🔍 Switched to mode: {current_mode.value}")
                    except ValueError:
                        print(f"❌ Invalid mode: {mode_name}")
                    continue
                
                if user_input.startswith('/docs'):
                    await self._show_documents()
                    continue
                
                if user_input.startswith('/analytics'):
                    await self._show_analytics()
                    continue
                
                # Execute query
                context = QueryContext(
                    persona=current_persona,
                    mode=current_mode
                )
                
                print("🔍 Processing query...")
                
                response = await self.query_engine.query(
                    user_input, context, conversation_id
                )
                
                # Update conversation ID for follow-up queries
                conversation_id = response.conversation_id
                
                # Display response
                self._display_response(response)
                
                # Show follow-up suggestions
                follow_ups = await self.query_engine.suggest_follow_up_questions(
                    user_input, response, context
                )
                
                if follow_ups:
                    print("\n💡 Suggested follow-up questions:")
                    for i, question in enumerate(follow_ups, 1):
                        print(f"   {i}. {question}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error processing query: {str(e)}")
    
    def _show_help(self):
        """Show help information"""
        print("""
📖 Covenantrix CLI Help:

Commands:
  /persona <name>  - Switch AI persona (legal_advisor, contract_analyst, risk_assessor, legal_writer, compliance_officer)
  /mode <name>     - Switch query mode (local, global, hybrid, naive, mix)
  /docs            - List processed documents
  /analytics       - Show query analytics
  help             - Show this help
  quit/exit/q      - Exit the session

Query Modes:
  • local   - Focus on specific entities and detailed information
  • global  - High-level themes and cross-document analysis
  • hybrid  - Best of both local and global (recommended)
  • naive   - Simple vector similarity search
  • mix     - Knowledge graph + vector retrieval

Personas:
  • legal_advisor     - General legal advice and risk assessment
  • contract_analyst  - Detailed contract breakdown and analysis
  • risk_assessor     - Focus on legal risks and mitigation
  • legal_writer      - Document drafting and improvement
  • compliance_officer - Regulatory compliance and standards

Examples:
  "What are the main obligations in this contract?"
  "Identify potential legal risks in the termination clause"
  "How can I improve the clarity of section 5?"
        """)
    
    async def _show_documents(self):
        """Show processed documents"""
        documents = await self.doc_processor.list_documents()
        
        if not documents:
            print("📄 No documents processed yet")
            return
        
        print(f"\n📚 Processed Documents ({len(documents)}):")
        print("-" * 80)
        
        for doc in documents[:10]:  # Show last 10
            print(f"📄 {doc.original_name}")
            print(f"   ID: {doc.id}")
            print(f"   Type: {doc.document_type}")
            print(f"   Folder: {doc.folder_id}")
            print(f"   Entities: {doc.entities_extracted}")
            print(f"   Processed: {doc.processed_at.strftime('%Y-%m-%d %H:%M')}")
            print()
        
        if len(documents) > 10:
            print(f"... and {len(documents) - 10} more documents")
    
    async def _show_analytics(self):
        """Show query analytics"""
        analytics = await self.query_engine.get_query_analytics()
        
        print("\n📊 Query Analytics:")
        print("-" * 40)
        
        if "message" in analytics:
            print(analytics["message"])
            return
        
        print(f"Total Queries: {analytics['total_queries']}")
        print(f"Avg Response Time: {analytics['average_response_time']}s")
        print(f"Avg Confidence: {analytics['average_confidence']:.2f}")
        
        print("\n🎭 Persona Usage:")
        for persona, count in analytics['persona_usage'].items():
            print(f"   {persona}: {count}")
        
        print("\n🔍 Mode Usage:")
        for mode, count in analytics['mode_usage'].items():
            print(f"   {mode}: {count}")
    
    def _display_response(self, response: QueryResponse):
        """Display formatted query response"""
        print(f"\n📝 Response (Confidence: {response.confidence_score:.2f}):")
        print("-" * 60)
        print(response.answer)
        
        if response.sources:
            print(f"\n📚 Sources ({len(response.sources)}):")
            for i, source in enumerate(response.sources, 1):
                print(f"   {i}. {source.get('excerpt', 'Source reference')}")
        
        print(f"\n⏱️  Response time: {response.processing_time:.2f}s")
        print(f"🎭 Persona: {response.persona_used}")
        print(f"🔍 Mode: {response.query_mode}")
    
    async def batch_test(self, test_file: str):
        """Run batch tests from JSON file"""
        if not self.initialized:
            await self.initialize()
        
        if not os.path.exists(test_file):
            print(f"❌ Test file not found: {test_file}")
            return
        
        with open(test_file, 'r') as f:
            tests = json.load(f)
        
        print(f"🧪 Running {len(tests)} batch tests...")
        
        results = []
        for i, test in enumerate(tests, 1):
            print(f"\n🧪 Test {i}/{len(tests)}: {test['name']}")
            
            context = QueryContext(
                persona=PersonaType(test.get('persona', 'legal_advisor')),
                mode=QueryMode(test.get('mode', 'hybrid'))
            )
            
            response = await self.query_engine.query(test['query'], context)
            
            result = {
                "test_name": test['name'],
                "query": test['query'],
                "persona": response.persona_used,
                "mode": response.query_mode,
                "confidence": response.confidence_score,
                "response_time": response.processing_time,
                "success": response.confidence_score > 0.5
            }
            
            results.append(result)
            
            print(f"   ✅ Confidence: {response.confidence_score:.2f}")
            print(f"   ⏱️  Time: {response.processing_time:.2f}s")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"test_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 Batch test completed! Results saved to: {results_file}")
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        avg_confidence = sum(r['confidence'] for r in results) / len(results)
        avg_time = sum(r['response_time'] for r in results) / len(results)
        
        print(f"✅ Success Rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
        print(f"📊 Avg Confidence: {avg_confidence:.2f}")
        print(f"⏱️  Avg Response Time: {avg_time:.2f}s")

async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Covenantrix RAG Service CLI")
    parser.add_argument('--process', nargs='+', help='Process document files')
    parser.add_argument('--folder', default='default', help='Folder ID for processed documents')
    parser.add_argument('--query', help='Execute a single query')
    parser.add_argument('--persona', default='legal_advisor', help='AI persona to use')
    parser.add_argument('--mode', default='hybrid', help='Query mode to use')
    parser.add_argument('--interactive', action='store_true', help='Start interactive session')
    parser.add_argument('--test', help='Run batch tests from JSON file')
    parser.add_argument('--server', action='store_true', help='Start FastAPI server')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    
    args = parser.parse_args()
    
    cli = CovenantrixCLI()
    
    try:
        if args.process:
            # Process documents
            results = await cli.process_documents(args.process, args.folder)
            print(f"\n📊 Processed {len(results)} documents successfully")
        
        elif args.query:
            # Single query
            await cli.initialize()
            context = QueryContext(
                persona=PersonaType(args.persona),
                mode=QueryMode(args.mode)
            )
            response = await cli.query_engine.query(args.query, context)
            cli._display_response(response)
        
        elif args.test:
            # Batch testing
            await cli.batch_test(args.test)
        
        elif args.server:
            # Start FastAPI server (implementation below)
            print(f"🚀 Starting FastAPI server on port {args.port}")
            print("📖 API documentation will be available at http://localhost:{}/docs".format(args.port))
            # TODO: Implement FastAPI server
            print("⚠️  FastAPI server implementation coming in next phase")
        
        else:
            # Default to interactive mode
            await cli.interactive_query()
    
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

def run_async_main():
    """Run the main async function with proper event loop handling"""
    try:
        # Try to get existing event loop
        loop = asyncio.get_running_loop()
        # If we get here, there's already a loop running
        print("❌ Error: Event loop is already running.")
        print("💡 Please run this script in a fresh terminal session.")
        return False
    except RuntimeError:
        # No event loop running, we can create one
        pass
    
    # Set up event loop policy for Windows compatibility
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
        return True
    except Exception as e:
        if "event loop is already running" in str(e).lower():
            print("❌ Error: Event loop conflict detected.")
            print("💡 Try running from a fresh terminal or restart your shell.")
            return False
        else:
            raise

if __name__ == "__main__":
    success = run_async_main()
    if not success:
        sys.exit(1)