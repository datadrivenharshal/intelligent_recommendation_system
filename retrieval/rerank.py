# retrieval/rerank.py
import google.generativeai as genai
import os
import sys
from typing import List, Tuple, Dict, Optional
import json
from dataclasses import dataclass
import re

# Ensure project root is on sys.path so local package imports work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from indexing.schema import Assessment
from retrieval.hybrid_retrieve import HybridRetriever
from config import config

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

class LLMReranker:
    def __init__(self):
        """Initialize LLM reranker with Gemini"""
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(config.LLM_MODEL)
        self.retriever = HybridRetriever()
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze query to extract requirements using LLM
        
        Args:
            query: Natural language query
            
        Returns:
            QueryAnalysis object
        """
        prompt = f"""
        Analyze this job description/query and extract key information:
        
        Query: "{query}"
        
        Extract:
        1. Primary job role/title (e.g., "Java Developer", "Sales Manager")
        2. Required technical skills (e.g., ["Java", "Python", "SQL"])
        3. Required behavioral/soft skills (e.g., ["communication", "teamwork"])
        4. Duration constraints if mentioned (e.g., "30 minutes", "1 hour")
        5. Preferred test types if mentioned (e.g., cognitive, personality, technical)
        
        Return as JSON with keys: role, technical_skills, behavioral_skills, 
        min_duration_minutes, max_duration_minutes, preferred_test_types.
        Use null for unknown values.
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis_dict = json.loads(json_match.group())
            else:
                analysis_dict = {}
            
            # Determine if query is technical/behavioral
            technical_skills = analysis_dict.get('technical_skills', [])
            behavioral_skills = analysis_dict.get('behavioral_skills', [])
            
            return QueryAnalysis(
                primary_role=analysis_dict.get('role', 'Unknown'),
                required_skills=technical_skills + behavioral_skills,
                is_technical=len(technical_skills) > 0,
                is_behavioral=len(behavioral_skills) > 0,
                min_duration=analysis_dict.get('min_duration_minutes'),
                max_duration=analysis_dict.get('max_duration_minutes'),
                test_types_preferred=analysis_dict.get('preferred_test_types', [])
            )
            
        except Exception as e:
            print(f"Error analyzing query: {e}")
            # Fallback to basic analysis
            return self._basic_query_analysis(query)
    
    def _basic_query_analysis(self, query: str) -> QueryAnalysis:
        """Basic query analysis without LLM"""
        query_lower = query.lower()
        
        # Extract duration
        min_duration = max_duration = None
        duration_match = re.search(r'(\d+)\s*(?:min|minute|hour)', query_lower)
        if duration_match:
            duration = int(duration_match.group(1))
            if 'hour' in query_lower:
                duration *= 60
            max_duration = duration
        
        # Extract role
        role = "Professional"
        role_keywords = {
            'developer': 'Developer',
            'engineer': 'Engineer',
            'analyst': 'Analyst',
            'manager': 'Manager',
            'sales': 'Sales Professional',
            'admin': 'Administrator',
            'consultant': 'Consultant'
        }
        
        for keyword, role_name in role_keywords.items():
            if keyword in query_lower:
                role = role_name
                break
        
        # Extract skills
        skills = []
        tech_skills = ['java', 'python', 'sql', 'javascript', 'html', 'css', 'selenium']
        behavioral_skills = ['communication', 'teamwork', 'leadership', 'collaboration', 'personality']
        
        for skill in tech_skills + behavioral_skills:
            if skill in query_lower:
                skills.append(skill)
        
        return QueryAnalysis(
            primary_role=role,
            required_skills=skills,
            is_technical=any(skill in tech_skills for skill in skills),
            is_behavioral=any(skill in behavioral_skills for skill in skills),
            min_duration=min_duration,
            max_duration=max_duration
        )
    
    def rerank_with_llm(self, 
                       query: str, 
                       candidates: List[Tuple[Assessment, float]], 
                       k: int = 10) -> List[Tuple[Assessment, float]]:
        """
        Rerank candidates using LLM scoring
        
        Args:
            query: Original query
            candidates: List of (assessment, similarity_score)
            k: Number of final results
            
        Returns:
            Reranked list of (assessment, combined_score)
        """
        if not candidates:
            return []
        
        # Analyze query
        query_analysis = self.analyze_query(query)
        
        # Score each candidate
        scored_candidates = []
        
        for assessment, sim_score in candidates:
            # Calculate relevance score based on multiple factors
            relevance_score = self._calculate_relevance_score(
                assessment, query_analysis, sim_score
            )
            
            scored_candidates.append((assessment, relevance_score))
        
        # Sort by combined score (descending)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        return scored_candidates[:k]
    
    def _calculate_relevance_score(self, 
                                 assessment: Assessment, 
                                 query_analysis: QueryAnalysis,
                                 similarity_score: float) -> float:
        """
        Calculate combined relevance score
        
        Args:
            assessment: Assessment object
            query_analysis: Analyzed query
            similarity_score: Semantic similarity (0-1)
            
        Returns:
            Combined relevance score (0-1)
        """
        weights = {
            'similarity': 0.4,
            'skill_match': 0.3,
            'duration_match': 0.15,
            'test_type_match': 0.15
        }
        
        # 1. Skill match score
        skill_score = 0.0
        if query_analysis.required_skills and assessment.skills:
            matched_skills = set(query_analysis.required_skills) & set(assessment.skills)
            if matched_skills:
                skill_score = len(matched_skills) / len(query_analysis.required_skills)
        
        # 2. Duration match score
        duration_score = 1.0  # Default: perfect match
        if query_analysis.min_duration and assessment.duration < query_analysis.min_duration:
            duration_score = 0.3  # Penalty for being too short
        if query_analysis.max_duration and assessment.duration > query_analysis.max_duration:
            duration_score = 0.3  # Penalty for being too long
        
        # 3. Test type match score
        type_score = 0.5  # Default neutral
        if query_analysis.test_types_preferred:
            matched_types = set(query_analysis.test_types_preferred) & set(assessment.test_type)
            if matched_types:
                type_score = 1.0
        elif query_analysis.is_technical and query_analysis.is_behavioral:
            # Mixed query: prefer assessments with both types
            has_technical = any(t in config.TECHNICAL_TYPES for t in assessment.test_type)
            has_behavioral = any(t in config.BEHAVIORAL_TYPES for t in assessment.test_type)
            if has_technical and has_behavioral:
                type_score = 1.0
            elif has_technical or has_behavioral:
                type_score = 0.7
        elif query_analysis.is_technical:
            # Technical query: prefer technical assessments
            if any(t in config.TECHNICAL_TYPES for t in assessment.test_type):
                type_score = 1.0
        elif query_analysis.is_behavioral:
            # Behavioral query: prefer behavioral assessments
            if any(t in config.BEHAVIORAL_TYPES for t in assessment.test_type):
                type_score = 1.0
        
        # Combine scores
        combined_score = (
            weights['similarity'] * similarity_score +
            weights['skill_match'] * skill_score +
            weights['duration_match'] * duration_score +
            weights['test_type_match'] * type_score
        )
        
        return min(combined_score, 1.0)  # Cap at 1.0
    
    def balance_recommendations(self, 
                               recommendations: List[Tuple[Assessment, float]]) -> List[Assessment]:
        """
        Ensure balanced mix of test types for diverse queries
        
        Args:
            recommendations: List of (assessment, score)
            
        Returns:
            Balanced list of assessments
        """
        if not recommendations:
            return []
        
        assessments = [assess for assess, _ in recommendations]
        
        # Check if we need balancing
        technical_count = sum(1 for a in assessments 
                            if any(t in config.TECHNICAL_TYPES for t in a.test_type))
        behavioral_count = sum(1 for a in assessments 
                             if any(t in config.BEHAVIORAL_TYPES for t in a.test_type))
        total = len(assessments)
        
        # If already balanced, return as is
        if (technical_count / total >= config.MIN_TECHNICAL_PCT and
            behavioral_count / total >= config.MIN_BEHAVIORAL_PCT):
            return assessments
        
        # Need balancing - reorder to mix types
        technical_assessments = []
        behavioral_assessments = []
        other_assessments = []
        
        for assessment in assessments:
            is_technical = any(t in config.TECHNICAL_TYPES for t in assessment.test_type)
            is_behavioral = any(t in config.BEHAVIORAL_TYPES for t in assessment.test_type)
            
            if is_technical and not is_behavioral:
                technical_assessments.append(assessment)
            elif is_behavioral and not is_technical:
                behavioral_assessments.append(assessment)
            else:
                other_assessments.append(assessment)
        
        # Create balanced mix
        balanced = []
        max_len = min(len(technical_assessments), len(behavioral_assessments))
        
        # Alternate between technical and behavioral
        for i in range(max_len):
            if i < len(technical_assessments):
                balanced.append(technical_assessments[i])
            if i < len(behavioral_assessments):
                balanced.append(behavioral_assessments[i])
        
        # Add remaining assessments
        remaining = (technical_assessments[max_len:] + 
                    behavioral_assessments[max_len:] + 
                    other_assessments)
        balanced.extend(remaining)
        
        return balanced[:config.MAX_RECOMMENDATIONS]
    
    def recommend(self, 
                 query: str, 
                 k: int = config.TOP_K_FINAL) -> List[Assessment]:
        """
        Complete recommendation pipeline with LLM enhancement
        
        Args:
            query: Natural language query
            k: Number of recommendations
            
        Returns:
            List of recommended assessments
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
        
        # Step 3: LLM reranking
        ranked = self.rerank_with_llm(query, candidates, k * 2)
        
        # Step 4: Balance recommendations
        balanced = self.balance_recommendations(ranked)
        
        # Step 5: Ensure minimum recommendations
        if len(balanced) < config.MIN_RECOMMENDATIONS and candidates:
            # Add top candidates by similarity if needed
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

def test_llm_reranker():
    """Test the LLM reranker"""
    # Set your Gemini API key
    import os
    os.environ['GEMINI_API_KEY'] = 'YOUR_API_KEY'  # Replace with actual key
    
    reranker = LLMReranker()
    
    test_queries = [
        "Java developer who can collaborate with business teams, 40 minutes",
        "Sales professional with communication skills",
        "Need cognitive and personality tests for analyst, 45 mins"
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
    test_llm_reranker()