# retrieval/rerank.py (Updated for Groq)
import re
import os
import sys
from typing import List, Tuple, Optional
from dataclasses import dataclass

# Ensure project root is on sys.path so local package imports work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from indexing.schema import Assessment
from retrieval.hybrid_retrieve import HybridRetriever
from retrieval.rules import RecommendationRules

# Simple config object with defaults
class Config:
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama3-70b-8192')
    TOP_K_RETRIEVE = 20
    TOP_K_FINAL = 10
    MIN_RECOMMENDATIONS = 3
    MAX_RECOMMENDATIONS = 10

config = Config()

@dataclass
class QueryAnalysis:
    """Analyzed query information"""
    primary_role: str
    required_skills: List[str]
    is_technical: bool = False
    is_behavioral: bool = False
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None
    test_types_preferred: List[str] = None
    
    def __post_init__(self):
        if self.test_types_preferred is None:
            self.test_types_preferred = []

class GroqReranker:
    def __init__(self, use_llm: bool = True):
        """
        Initialize reranker with optional Groq LLM
        
        Args:
            use_llm: Whether to use Groq LLM or fallback to rules
        """
        self.retriever = HybridRetriever()
        self.use_llm = use_llm
        
        if use_llm and config.GROQ_API_KEY:
            from llm.groq_client import GroqClient
            self.llm_client = GroqClient(
                api_key=config.GROQ_API_KEY,
                model=config.GROQ_MODEL
            )
        else:
            self.llm_client = None
            print("Groq LLM disabled. Using rule-based analysis.")
        
        # Fallback rule-based analyzer
        self.rule_analyzer = RuleBasedAnalyzer()
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze query using Groq LLM or fallback to rules
        """
        if self.llm_client and self.use_llm:
            try:
                analysis = self.llm_client.analyze_query(query)
                
                # Convert to QueryAnalysis format
                is_technical = len(analysis.get("technical_skills", [])) > 0
                is_behavioral = len(analysis.get("behavioral_skills", [])) > 0
                all_skills = analysis.get("technical_skills", []) + analysis.get("behavioral_skills", [])
                
                duration_constraints = analysis.get("duration_constraints", {})
                
                return QueryAnalysis(
                    primary_role=analysis.get("primary_role", "Professional"),
                    required_skills=all_skills,
                    is_technical=is_technical,
                    is_behavioral=is_behavioral,
                    min_duration=duration_constraints.get("min_duration_minutes"),
                    max_duration=duration_constraints.get("max_duration_minutes"),
                    test_types_preferred=analysis.get("preferred_test_types", [])
                )
                
            except Exception as e:
                print(f"Groq LLM analysis failed: {e}. Falling back to rules.")
                # Fallback to rule-based
                return self.rule_analyzer.analyze_query(query)
        else:
            # Use rule-based analysis
            return self.rule_analyzer.analyze_query(query)
    
    def rerank_with_llm_scoring(self, 
                               query: str, 
                               candidates: List[Tuple[Assessment, float]], 
                               k: int = 10) -> List[Tuple[Assessment, float]]:
        """
        Rerank candidates using Groq LLM scoring
        """
        if not candidates or not self.llm_client:
            return candidates[:k]
        
        scored_candidates = []
        
        for assessment, sim_score in candidates:
            # Get LLM relevance scores
            llm_scores = self.llm_client.score_assessment_relevance(
                query=query,
                assessment_description=assessment.description,
                assessment_skills=assessment.skills or []
            )
            
            # Combine LLM score with similarity score
            llm_weight = 0.6
            sim_weight = 0.4
            
            combined_score = (
                llm_weight * llm_scores.get("overall_relevance", 0.5) +
                sim_weight * sim_score
            )
            
            scored_candidates.append((assessment, combined_score))
        
        # Sort by combined score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:k]
    
    def rerank_with_rules(self, 
                         query: str, 
                         candidates: List[Tuple[Assessment, float]], 
                         k: int = 10) -> List[Tuple[Assessment, float]]:
        """Rerank using rule-based scoring"""
        return self.rule_analyzer.rerank_with_rules(query, candidates, k)
    
    def recommend(self, 
                 query: str, 
                 k: int = config.TOP_K_FINAL,
                 use_llm_rerank: bool = True) -> List[Assessment]:
        """
        Complete recommendation pipeline with Groq LLM enhancement
        """
        print(f"Processing query: {query}")
        
        # Step 1: Analyze query
        query_analysis = self.analyze_query(query)
        print(f"Query analysis: {query_analysis}")
        
        # Step 2: Initial retrieval
        candidates = self.retriever.retrieve(
            query=query,
            k=config.TOP_K_RETRIEVE,
            max_duration=query_analysis.max_duration,
            min_duration=query_analysis.min_duration,
            test_types=query_analysis.test_types_preferred
        )
        
        if not candidates:
            print("No candidates found")
            return []
        
        print(f"Retrieved {len(candidates)} candidates")
        
        # Step 3: Rerank (LLM or rules)
        if use_llm_rerank and self.llm_client:
            ranked = self.rerank_with_llm_scoring(query, candidates, k * 2)
        else:
            ranked = self.rerank_with_rules(query, candidates, k * 2)
        
        # Step 4: Balance recommendations
        balanced_results = RecommendationRules.balance_knowledge_personality(ranked, query)
        balanced = [assess for assess, _ in balanced_results]
        
        # Step 5: Ensure minimum recommendations
        if len(balanced) < config.MIN_RECOMMENDATIONS and candidates:
            additional = [assess for assess, _ in candidates[:config.MIN_RECOMMENDATIONS - len(balanced)]]
            balanced.extend(additional)
        
        # Remove duplicates while preserving order
        seen = set()
        final = []
        for assess in balanced:
            if assess.id not in seen:
                seen.add(assess.id)
                final.append(assess)
        
        return final[:k]

class RuleBasedAnalyzer:
    """Rule-based analyzer (fallback when LLM not available)"""
    
    def __init__(self):
        self.tech_skill_keywords = {
            'java', 'python', 'sql', 'javascript', 'html', 'css', 'selenium',
            'c++', 'c#', 'ruby', 'php', 'react', 'angular', 'vue', 'node',
            'database', 'aws', 'azure', 'docker', 'kubernetes', 'git'
        }
        
        self.behavioral_skill_keywords = {
            'communication', 'teamwork', 'leadership', 'collaboration', 'personality',
            'cognitive', 'behavioral', 'soft skill', 'interpersonal', 'adaptability'
        }
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """Rule-based query analysis"""
        query_lower = query.lower()
        
        # Extract duration
        min_duration, max_duration = self._extract_duration(query_lower)
        
        # Extract skills
        required_skills = []
        for skill in self.tech_skill_keywords:
            if skill in query_lower:
                required_skills.append(skill)
        for skill in self.behavioral_skill_keywords:
            if skill in query_lower:
                required_skills.append(skill)
        
        # Determine category
        is_technical = any(s in self.tech_skill_keywords for s in required_skills)
        is_behavioral = any(s in self.behavioral_skill_keywords for s in required_skills)
        
        # Extract role
        primary_role = "Professional"
        if 'sales' in query_lower:
            primary_role = "Sales Professional"
        elif 'analyst' in query_lower:
            primary_role = "Analyst"
        elif 'developer' in query_lower or 'java' in query_lower or 'python' in query_lower:
            primary_role = "Developer"
        elif 'manager' in query_lower:
            primary_role = "Manager"
        
        return QueryAnalysis(
            primary_role=primary_role,
            required_skills=required_skills,
            is_technical=is_technical,
            is_behavioral=is_behavioral,
            min_duration=min_duration,
            max_duration=max_duration,
            test_types_preferred=[]
        )
    
    def _extract_duration(self, query: str):
        """Extract duration from query"""
        import re
        min_duration = max_duration = None
        
        patterns = [
            (r'(\d+)\s*(?:minute|min)\s*(?:max|maximum)', 'max'),
            (r'(\d+)\s*(?:hour|hr)\s*(?:max|maximum)', 'max_hour'),
            (r'(\d+)[-\s](\d+)\s*(?:minute|min)', 'range'),
            (r'(\d+)\s*(?:minute|min)', 'max')
        ]
        
        for pattern, pattern_type in patterns:
            match = re.search(pattern, query)
            if match:
                if pattern_type == 'max':
                    max_duration = int(match.group(1))
                elif pattern_type == 'max_hour':
                    max_duration = int(match.group(1)) * 60
                elif pattern_type == 'range':
                    min_duration = int(match.group(1))
                    max_duration = int(match.group(2))
                break
        
        return min_duration, max_duration
    
    def rerank_with_rules(self, query, candidates, k):
        """Rule-based reranking"""
        query_analysis = self.analyze_query(query)
        scored = []
        
        for assessment, sim_score in candidates:
            # Simple scoring based on skill matches
            skill_score = 0
            if query_analysis.required_skills and assessment.skills:
                matched = set(query_analysis.required_skills) & set(assessment.skills)
                skill_score = len(matched) / len(query_analysis.required_skills) if query_analysis.required_skills else 0
            
            # Duration penalty
            duration_score = 1
            if query_analysis.max_duration and assessment.duration > query_analysis.max_duration:
                duration_score = 0.3
            
            combined = 0.4 * sim_score + 0.3 * skill_score + 0.3 * duration_score
            scored.append((assessment, combined))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

def test_groq_reranker():
    """Test the Groq reranker"""
    import os
    
    # Set your Groq API key
    os.environ['GROQ_API_KEY'] = 'your_groq_api_key_here'  # Get from https://console.groq.com
    
    reranker = GroqReranker(use_llm=True)
    
    test_queries = [
        "Java developer who can collaborate with business teams, 40 minutes",
        "Sales professional with communication skills",
        "Need cognitive and personality tests for analyst, 45 mins",
        "Data analyst with SQL and Python skills, 1 hour max"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        recommendations = reranker.recommend(query, k=5)
        
        for i, assessment in enumerate(recommendations, 1):
            print(f"{i}. {assessment.assessment_name}")
            print(f"   URL: {assessment.url}")
            print(f"   Duration: {assessment.duration}min")
            print(f"   Test Types: {', '.join(assessment.test_type)}")
            print(f"   Skills: {assessment.skills or 'N/A'}")
            print()

if __name__ == "__main__":
    test_groq_reranker()