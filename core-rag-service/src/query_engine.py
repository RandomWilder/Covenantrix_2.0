# core-rag-service/src/query_engine.py
"""
Core query engine for Covenantrix with persona management
Handles intelligent document querying with legal domain expertise
"""

import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from lightrag import QueryParam
from lightrag.llm.openai import gpt_4o_mini_complete, gpt_4o_complete

class QueryMode(Enum):
    """Query modes for different retrieval strategies"""
    LOCAL = "local"      # Specific entity-focused queries
    GLOBAL = "global"    # High-level thematic queries
    HYBRID = "hybrid"    # Best of both worlds
    NAIVE = "naive"      # Simple vector similarity
    MIX = "mix"          # Knowledge graph + vector retrieval

class PersonaType(Enum):
    """AI Persona types for specialized legal assistance"""
    LEGAL_ADVISOR = "legal_advisor"
    LEGAL_WRITER = "legal_writer"
    CONTRACT_ANALYST = "contract_analyst"
    RISK_ASSESSOR = "risk_assessor"
    COMPLIANCE_OFFICER = "compliance_officer"

@dataclass
class QueryContext:
    """Context for query execution"""
    document_ids: Optional[List[str]] = None
    folder_id: Optional[str] = None
    document_types: Optional[List[str]] = None
    date_range: Optional[tuple] = None
    persona: PersonaType = PersonaType.LEGAL_ADVISOR
    mode: QueryMode = QueryMode.HYBRID
    max_tokens: int = 4000
    include_citations: bool = True

@dataclass
class QueryResponse:
    """Structured response from query execution"""
    answer: str
    sources: List[Dict[str, Any]]
    confidence_score: float
    query_mode: str
    persona_used: str
    processing_time: float
    tokens_used: int
    conversation_id: str
    timestamp: datetime = field(default_factory=datetime.now)

class PersonaManager:
    """
    Manages different AI personas for specialized legal assistance
    """
    
    def __init__(self):
        self.personas = self._initialize_personas()
        
    def _initialize_personas(self) -> Dict[PersonaType, Dict]:
        """Initialize persona configurations"""
        return {
            PersonaType.LEGAL_ADVISOR: {
                "system_prompt": """You are a senior legal advisor with 20+ years of experience in contract law, 
                corporate law, and legal risk assessment. You provide precise, actionable legal advice based on 
                the provided documents. Always cite specific clauses, sections, or provisions when making 
                recommendations. Focus on practical implications and potential risks.""",
                
                "model_func": gpt_4o_mini_complete,
                "temperature": 0.1,  # Lower for precision
                "response_style": "detailed_analysis",
                "specialties": ["contract_review", "risk_assessment", "legal_compliance"]
            },
            
            PersonaType.LEGAL_WRITER: {
                "system_prompt": """You are an expert legal writer specializing in drafting, editing, and 
                improving legal documents. You help create clear, enforceable legal language while maintaining 
                precision and completeness. Focus on structure, clarity, and legal soundness. Suggest specific 
                improvements and alternative phrasings.""",
                
                "model_func": gpt_4o_complete,  # Higher model for creative writing
                "temperature": 0.3,  # Slightly higher for creativity
                "response_style": "constructive_editing",
                "specialties": ["document_drafting", "clause_improvement", "legal_writing"]
            },
            
            PersonaType.CONTRACT_ANALYST: {
                "system_prompt": """You are a specialized contract analyst who excels at breaking down complex 
                agreements, identifying key terms, obligations, and potential issues. You provide systematic 
                analysis of contract components including parties, consideration, performance requirements, 
                termination conditions, and dispute resolution mechanisms.""",
                
                "model_func": gpt_4o_mini_complete,
                "temperature": 0.1,
                "response_style": "systematic_breakdown",
                "specialties": ["contract_analysis", "term_extraction", "obligation_mapping"]
            },
            
            PersonaType.RISK_ASSESSOR: {
                "system_prompt": """You are a legal risk assessment specialist who identifies, evaluates, and 
                prioritizes legal risks in documents and business arrangements. You assess probability and impact 
                of potential legal issues, suggest mitigation strategies, and provide risk ratings with clear 
                justifications.""",
                
                "model_func": gpt_4o_mini_complete,
                "temperature": 0.1,
                "response_style": "risk_focused_analysis",
                "specialties": ["risk_identification", "impact_assessment", "mitigation_strategies"]
            },
            
            PersonaType.COMPLIANCE_OFFICER: {
                "system_prompt": """You are a compliance officer specialized in regulatory requirements, 
                industry standards, and legal compliance verification. You identify compliance gaps, 
                regulatory requirements, and ensure documents meet applicable legal standards. You stay 
                current with regulatory changes and industry best practices.""",
                
                "model_func": gpt_4o_mini_complete,
                "temperature": 0.1,
                "response_style": "compliance_checklist",
                "specialties": ["regulatory_compliance", "standards_verification", "gap_analysis"]
            }
        }
    
    def get_persona_config(self, persona: PersonaType) -> Dict:
        """Get configuration for a specific persona"""
        return self.personas.get(persona, self.personas[PersonaType.LEGAL_ADVISOR])
    
    def get_enhanced_prompt(self, persona: PersonaType, query: str, context: str = "") -> str:
        """Generate enhanced prompt with persona-specific instructions"""
        config = self.get_persona_config(persona)
        
        # Detect Hebrew text
        is_hebrew = self._detect_hebrew(query)
        language_instruction = ""
        
        if is_hebrew:
            language_instruction = "\n\n🇮🇱 CRITICAL HEBREW RESPONSE REQUIREMENT 🇮🇱\n=== YOU MUST RESPOND IN HEBREW ===\n- The user query is in Hebrew\n- Your ENTIRE response must be in Hebrew\n- Use professional Hebrew legal terminology\n- Do NOT translate to English\n- Maintain RTL text direction\n- This is mandatory - Hebrew queries require Hebrew responses"
        
        enhanced_prompt = f"""{config['system_prompt']}{language_instruction}

CONTEXT INFORMATION:
{context}

USER QUERY: {query}

Please provide a response that:
1. Directly addresses the query with {config['response_style']}
2. Cites specific sources and sections when available
3. Focuses on your specialty areas: {', '.join(config['specialties'])}
4. Provides actionable insights appropriate for a legal professional
5. {"** MANDATORY: Respond ONLY in Hebrew using proper legal terminology **" if is_hebrew else "Responds in English"}

RESPONSE:"""
        
        return enhanced_prompt
    
    def _detect_hebrew(self, text: str) -> bool:
        """Detect if text contains Hebrew characters"""
        hebrew_chars = 0
        total_chars = 0
        
        for char in text:
            if char.isalpha():
                total_chars += 1
                # Hebrew Unicode range: U+0590 to U+05FF
                if '\u0590' <= char <= '\u05FF':
                    hebrew_chars += 1
        
        # Consider text Hebrew if more than 30% of alphabetic characters are Hebrew
        if total_chars > 0:
            return (hebrew_chars / total_chars) > 0.3
        return False

class ConversationManager:
    """
    Manages conversation history and context for multi-turn dialogues
    """
    
    def __init__(self):
        self.conversations = {}
        self.max_history_length = 10
    
    def create_conversation(self, persona: PersonaType) -> str:
        """Create a new conversation with a specific persona"""
        conv_id = f"{persona.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.conversations[conv_id] = {
            "persona": persona,
            "history": [],
            "created_at": datetime.now(),
            "last_updated": datetime.now()
        }
        return conv_id
    
    def add_exchange(self, conv_id: str, query: str, response: str):
        """Add a query-response exchange to conversation history"""
        if conv_id in self.conversations:
            self.conversations[conv_id]["history"].append({
                "query": query,
                "response": response,
                "timestamp": datetime.now()
            })
            
            # Trim history if too long
            if len(self.conversations[conv_id]["history"]) > self.max_history_length:
                self.conversations[conv_id]["history"] = \
                    self.conversations[conv_id]["history"][-self.max_history_length:]
            
            self.conversations[conv_id]["last_updated"] = datetime.now()
    
    def get_conversation_context(self, conv_id: str, max_exchanges: int = 3) -> List[Dict]:
        """Get recent conversation context for multi-turn queries"""
        if conv_id not in self.conversations:
            return []
        
        history = self.conversations[conv_id]["history"]
        return history[-max_exchanges:] if history else []

class QueryEngine:
    """
    Core query engine for Covenantrix RAG system
    """
    
    def __init__(self, document_processor):
        self.document_processor = document_processor
        self.persona_manager = PersonaManager()
        self.conversation_manager = ConversationManager()
        self.query_history = []
    
    async def query(
        self, 
        query: str, 
        context: QueryContext,
        conversation_id: Optional[str] = None
    ) -> QueryResponse:
        """
        Execute a query with specified context and persona
        """
        start_time = datetime.now()
        
        # Create new conversation if none provided
        if conversation_id is None:
            conversation_id = self.conversation_manager.create_conversation(context.persona)
        
        # Get persona configuration
        persona_config = self.persona_manager.get_persona_config(context.persona)
        
        # Build query parameters for LightRAG
        query_params = self._build_lightrag_params(context)
        
        # Get conversation context for multi-turn queries
        conv_context = self.conversation_manager.get_conversation_context(conversation_id)
        
        # Enhanced prompt with persona and context
        enhanced_query = self._build_enhanced_query(query, context, conv_context)
        
        try:
            # Execute query through LightRAG
            raw_response = await self.document_processor.rag.aquery(
                enhanced_query,
                param=query_params
            )
            
            # Process and structure response
            response = self._process_response(
                raw_response, 
                query, 
                context, 
                conversation_id, 
                start_time
            )
            
            # Add to conversation history
            self.conversation_manager.add_exchange(
                conversation_id, 
                query, 
                response.answer
            )
            
            # Log query for analytics
            self._log_query(query, context, response)
            
            return response
            
        except Exception as e:
            # Handle errors gracefully
            processing_time = (datetime.now() - start_time).total_seconds()
            error_response = QueryResponse(
                answer=f"I apologize, but I encountered an error processing your query: {str(e)}",
                sources=[],
                confidence_score=0.0,
                query_mode=context.mode.value,
                persona_used=context.persona.value,
                processing_time=processing_time,
                tokens_used=0,
                conversation_id=conversation_id
            )
            
            # Log the error for debugging
            self._log_query(query, context, error_response)
            
            return error_response
    
    def _build_lightrag_params(self, context: QueryContext) -> QueryParam:
        """Build LightRAG query parameters from context"""
        
        # Build conversation history for LightRAG
        conv_history = []
        if hasattr(context, 'conversation_id') and context.conversation_id:
            recent_context = self.conversation_manager.get_conversation_context(
                context.conversation_id, 2
            )
            for exchange in recent_context:
                conv_history.extend([
                    {"role": "user", "content": exchange["query"]},
                    {"role": "assistant", "content": exchange["response"]}
                ])
        
        return QueryParam(
            mode=context.mode.value,
            top_k=60,  # Retrieve more entities for legal precision
            chunk_top_k=15,  # More text chunks for comprehensive analysis
            max_entity_tokens=12000,  # Higher for complex legal entities
            max_relation_tokens=12000,  # Higher for relationship analysis
            max_total_tokens=context.max_tokens,
            conversation_history=conv_history,
            response_type="Multiple Paragraphs",
            enable_rerank=True  # Enable reranking for better relevance
        )
    
    def _build_enhanced_query(
        self, 
        query: str, 
        context: QueryContext, 
        conv_context: List[Dict]
    ) -> str:
        """Build enhanced query with persona and context"""
        
        # Base context information
        context_info = ""
        
        if context.document_ids:
            context_info += f"Focus on documents: {', '.join(context.document_ids[:5])}\n"
        
        if context.folder_id:
            context_info += f"Folder context: {context.folder_id}\n"
        
        if context.document_types:
            context_info += f"Document types: {', '.join(context.document_types)}\n"
        
        if conv_context:
            context_info += "\nRecent conversation context:\n"
            for exchange in conv_context[-2:]:  # Last 2 exchanges
                context_info += f"Q: {exchange['query'][:100]}...\n"
                context_info += f"A: {exchange['response'][:100]}...\n\n"
        
        # Get persona-enhanced prompt
        enhanced_query = self.persona_manager.get_enhanced_prompt(
            context.persona, 
            query, 
            context_info
        )
        
        return enhanced_query
    
    def _process_response(
        self, 
        raw_response: str, 
        original_query: str, 
        context: QueryContext, 
        conversation_id: str, 
        start_time: datetime
    ) -> QueryResponse:
        """Process raw LightRAG response into structured format"""
        
        # Extract sources and citations (simplified implementation)
        # In production, you'd parse LightRAG's citation format
        sources = self._extract_sources(raw_response)
        
        # Calculate confidence score based on response quality
        confidence_score = self._calculate_confidence(raw_response, sources)
        
        # Estimate token usage (simplified)
        tokens_used = len(raw_response.split()) * 1.3  # Rough approximation
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return QueryResponse(
            answer=raw_response,
            sources=sources,
            confidence_score=confidence_score,
            query_mode=context.mode.value,
            persona_used=context.persona.value,
            processing_time=processing_time,
            tokens_used=int(tokens_used),
            conversation_id=conversation_id
        )
    
    def _extract_sources(self, response: str) -> List[Dict[str, Any]]:
        """Extract source citations from response"""
        # Simplified implementation - in production, parse LightRAG citations
        sources = []
        
        # Look for common citation patterns
        if "based on" in response.lower() or "according to" in response.lower():
            sources.append({
                "type": "document_reference",
                "confidence": 0.8,
                "excerpt": "Document reference found in response"
            })
        
        return sources
    
    def _calculate_confidence(self, response: str, sources: List[Dict]) -> float:
        """Calculate confidence score for response"""
        base_confidence = 0.5
        
        # Increase confidence based on sources
        if sources:
            base_confidence += 0.2 * min(len(sources), 3)  # Max 0.6 boost from sources
        
        # Increase confidence based on response quality indicators
        quality_indicators = [
            "specific", "section", "clause", "provision", "according to",
            "based on", "as stated in", "the document indicates"
        ]
        
        found_indicators = sum(1 for indicator in quality_indicators 
                              if indicator in response.lower())
        base_confidence += 0.05 * min(found_indicators, 4)  # Max 0.2 boost
        
        # Decrease confidence for uncertainty indicators
        uncertainty_indicators = [
            "might", "could", "possibly", "unclear", "ambiguous", "uncertain"
        ]
        
        found_uncertainty = sum(1 for indicator in uncertainty_indicators 
                               if indicator in response.lower())
        base_confidence -= 0.1 * min(found_uncertainty, 2)  # Max 0.2 reduction
        
        return max(0.1, min(1.0, base_confidence))  # Clamp between 0.1 and 1.0
    
    def _log_query(self, query: str, context: QueryContext, response: QueryResponse):
        """Log query for analytics and improvement"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "persona": context.persona.value,
            "mode": context.mode.value,
            "response_time": response.processing_time,
            "confidence": response.confidence_score,
            "tokens_used": response.tokens_used,
            "sources_count": len(response.sources)
        }
        
        self.query_history.append(log_entry)
        
        # Keep only last 1000 queries in memory
        if len(self.query_history) > 1000:
            self.query_history = self.query_history[-1000:]
    
    async def get_query_analytics(self) -> Dict[str, Any]:
        """Get analytics about query performance"""
        if not self.query_history:
            return {"message": "No queries logged yet"}
        
        total_queries = len(self.query_history)
        avg_response_time = sum(q["response_time"] for q in self.query_history) / total_queries
        avg_confidence = sum(q["confidence"] for q in self.query_history) / total_queries
        
        # Persona usage statistics
        persona_stats = {}
        for query in self.query_history:
            persona = query["persona"]
            if persona not in persona_stats:
                persona_stats[persona] = 0
            persona_stats[persona] += 1
        
        # Mode usage statistics
        mode_stats = {}
        for query in self.query_history:
            mode = query["mode"]
            if mode not in mode_stats:
                mode_stats[mode] = 0
            mode_stats[mode] += 1
        
        return {
            "total_queries": total_queries,
            "average_response_time": round(avg_response_time, 2),
            "average_confidence": round(avg_confidence, 2),
            "persona_usage": persona_stats,
            "mode_usage": mode_stats,
            "recent_queries": self.query_history[-10:]  # Last 10 queries
        }
    
    async def suggest_follow_up_questions(
        self, 
        original_query: str, 
        response: QueryResponse,
        context: QueryContext
    ) -> List[str]:
        """Generate intelligent follow-up questions based on the response"""
        
        # Build context for follow-up generation
        follow_up_prompt = f"""Based on this legal query and response, suggest 3 relevant follow-up questions that a legal professional might ask:

Original Query: {original_query}

Response Summary: {response.answer[:500]}...

Persona Context: {context.persona.value}

Please suggest specific, actionable follow-up questions that would help the user get more detailed or related information. Focus on practical legal concerns."""

        try:
            # Use the same LLM to generate follow-ups
            # Get the LLM function from the RAG instance
            llm_func = self.document_processor.rag.llm_model_func
            
            # Call the LLM function properly
            if asyncio.iscoroutinefunction(llm_func):
                follow_up_response = await llm_func(
                    follow_up_prompt,
                    system_prompt="You are a helpful legal assistant that suggests relevant follow-up questions.",
                    history_messages=[],
                    max_tokens=300
                )
            else:
                follow_up_response = llm_func(
                    follow_up_prompt,
                    system_prompt="You are a helpful legal assistant that suggests relevant follow-up questions.",
                    history_messages=[],
                    max_tokens=300
                )
            
            # Parse the response into a list (simplified)
            # In production, you'd use more sophisticated parsing
            lines = follow_up_response.strip().split('\n')
            questions = []
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('1.') or line.startswith('2.') or line.startswith('3.')):
                    # Clean up the question
                    question = line.lstrip('- 123.').strip()
                    if question:
                        questions.append(question)
            
            return questions[:3]  # Return max 3 questions
            
        except Exception as e:
            # Fallback to generic questions based on persona
            return self._get_fallback_questions(context.persona)
    
    def _get_fallback_questions(self, persona: PersonaType) -> List[str]:
        """Get fallback follow-up questions based on persona"""
        fallback_questions = {
            PersonaType.LEGAL_ADVISOR: [
                "What are the potential legal risks in this situation?",
                "Are there any compliance requirements I should be aware of?",
                "What would you recommend as next steps?"
            ],
            PersonaType.CONTRACT_ANALYST: [
                "What are the key obligations for each party?",
                "Are there any problematic clauses I should review?",
                "How does this compare to standard industry contracts?"
            ],
            PersonaType.RISK_ASSESSOR: [
                "What is the overall risk level of this arrangement?",
                "What mitigation strategies would you recommend?",
                "Are there any red flags I should be concerned about?"
            ],
            PersonaType.LEGAL_WRITER: [
                "How can this language be improved for clarity?",
                "Are there any standard clauses that should be added?",
                "What alternative phrasings would you suggest?"
            ],
            PersonaType.COMPLIANCE_OFFICER: [
                "What regulatory requirements apply here?",
                "Are there any compliance gaps I should address?",
                "What documentation is needed for compliance?"
            ]
        }
        
        return fallback_questions.get(persona, fallback_questions[PersonaType.LEGAL_ADVISOR])

# Advanced Query Utilities
class QueryBuilder:
    """Helper class for building complex queries"""
    
    @staticmethod
    def contract_analysis_query(contract_type: str = "general") -> str:
        """Build a comprehensive contract analysis query"""
        return f"""Please provide a comprehensive analysis of this {contract_type} contract, including:

1. **Parties and Roles**: Who are the contracting parties and what are their primary obligations?
2. **Key Terms**: What are the essential terms, conditions, and performance requirements?
3. **Financial Aspects**: Payment terms, amounts, penalties, and financial obligations
4. **Timeline and Deadlines**: Important dates, deadlines, and duration of the agreement
5. **Risk Assessment**: Potential legal risks and problematic clauses
6. **Compliance Issues**: Any regulatory or legal compliance requirements
7. **Termination Provisions**: How and when can the contract be terminated?
8. **Dispute Resolution**: What mechanisms exist for resolving disputes?

Please provide specific references to clauses and sections where possible."""
    
    @staticmethod
    def risk_assessment_query() -> str:
        """Build a focused risk assessment query"""
        return """Please conduct a thorough legal risk assessment of the provided documents, focusing on:

1. **High-Risk Clauses**: Identify any provisions that could expose parties to significant legal or financial risk
2. **Missing Protections**: What standard protective clauses or provisions are absent?
3. **Compliance Risks**: Are there any regulatory compliance issues or gaps?
4. **Enforceability Concerns**: Are there any clauses that might be difficult to enforce?
5. **Liability Exposure**: What are the potential liability exposures for each party?
6. **Mitigation Recommendations**: Specific suggestions for reducing identified risks

Please rate each risk as HIGH, MEDIUM, or LOW and provide justification for each rating."""
    
    @staticmethod
    def compliance_check_query(industry: str = "general") -> str:
        """Build a compliance-focused query"""
        return f"""Please review the provided documents for compliance with {industry} industry standards and general legal requirements:

1. **Regulatory Compliance**: Does the document meet applicable regulatory requirements?
2. **Industry Standards**: How does it align with {industry} industry best practices?
3. **Legal Requirements**: Are all necessary legal provisions included?
4. **Documentation Requirements**: What additional documentation might be needed?
5. **Compliance Gaps**: What areas need attention to ensure full compliance?
6. **Recommendations**: Specific steps to achieve or maintain compliance

Please highlight any areas of non-compliance or concern."""

# Example usage and testing
async def test_query_engine():
    """Test function for the query engine"""
    from document_processor import DocumentProcessor
    
    # Initialize components
    doc_processor = DocumentProcessor()
    await doc_processor.initialize()
    
    query_engine = QueryEngine(doc_processor)
    
    # Test different personas and query modes
    test_queries = [
        {
            "query": "What are the main obligations of each party in this contract?",
            "context": QueryContext(
                persona=PersonaType.CONTRACT_ANALYST,
                mode=QueryMode.HYBRID
            )
        },
        {
            "query": "What legal risks should I be concerned about?",
            "context": QueryContext(
                persona=PersonaType.RISK_ASSESSOR,
                mode=QueryMode.GLOBAL
            )
        },
        {
            "query": "How can I improve the clarity of the termination clause?",
            "context": QueryContext(
                persona=PersonaType.LEGAL_WRITER,
                mode=QueryMode.LOCAL
            )
        }
    ]
    
    for test in test_queries:
        print(f"\n📋 Testing Query: {test['query']}")
        print(f"🎭 Persona: {test['context'].persona.value}")
        print(f"🔍 Mode: {test['context'].mode.value}")
        
        response = await query_engine.query(test['query'], test['context'])
        
        print(f"⏱️  Response Time: {response.processing_time:.2f}s")
        print(f"🎯 Confidence: {response.confidence_score:.2f}")
        print(f"📄 Answer: {response.answer[:200]}...")
        
        # Test follow-up suggestions
        follow_ups = await query_engine.suggest_follow_up_questions(
            test['query'], response, test['context']
        )
        print(f"❓ Follow-up Questions: {follow_ups}")
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_query_engine())