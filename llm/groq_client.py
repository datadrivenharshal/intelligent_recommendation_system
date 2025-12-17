# llm/groq_client.py
import os
from typing import List, Dict, Any, Optional
import json
import re
from groq import Groq

class GroqClient:
    """Client for Groq Cloud API"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama3-70b-8192"):
        """
        Initialize Groq client
        
        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var)
            model: Model to use
        """
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.client = Groq(api_key=api_key)
        self.model = model
        self.max_tokens = 1024
        self.temperature = 0.1  # Low temperature for consistent analysis
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze job query using Groq LLM
        
        Args:
            query: Natural language query or job description
            
        Returns:
            Dictionary with extracted information
        """
        prompt = f"""
        Analyze this job description/query and extract structured information.
        
        QUERY: "{query}"
        
        Extract the following information as a JSON object:
        1. "primary_role": The main job title/role (e.g., "Java Developer", "Sales Manager")
        2. "technical_skills": List of required technical skills/hard skills
        3. "behavioral_skills": List of required behavioral/soft skills
        4. "duration_constraints": Object with "min_duration_minutes" and "max_duration_minutes" (null if unspecified)
        5. "preferred_test_types": List of assessment types mentioned (e.g., "cognitive", "personality", "technical", "behavioral")
        6. "query_category": One of ["technical", "behavioral", "mixed"] based on skills mentioned
        
        Return ONLY the JSON object. No explanations.
        Example format:
        {{
            "primary_role": "Java Developer",
            "technical_skills": ["java", "spring", "sql"],
            "behavioral_skills": ["communication", "teamwork"],
            "duration_constraints": {{"min_duration_minutes": null, "max_duration_minutes": 45}},
            "preferred_test_types": ["cognitive", "technical"],
            "query_category": "mixed"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert HR analyst specializing in test assessment matching. Extract structured information from job queries."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            response_text = response.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return analysis
            else:
                # Fallback to basic parsing
                return self._fallback_analysis(query)
                
        except Exception as e:
            print(f"Error analyzing query with Groq: {e}")
            return self._fallback_analysis(query)
    
    def _fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis when LLM fails"""
        query_lower = query.lower()
        
        # Basic skill extraction
        tech_skills = []
        behavioral_skills = []
        
        tech_keywords = ['java', 'python', 'sql', 'javascript', 'html', 'css', 'selenium', 
                        'aws', 'azure', 'docker', 'kubernetes', 'react', 'angular']
        behavioral_keywords = ['communication', 'teamwork', 'leadership', 'collaboration', 
                              'personality', 'cognitive', 'behavioral', 'soft skill']
        
        for skill in tech_keywords:
            if skill in query_lower:
                tech_skills.append(skill)
        
        for skill in behavioral_keywords:
            if skill in query_lower:
                behavioral_skills.append(skill)
        
        # Duration extraction
        min_duration = max_duration = None
        duration_match = re.search(r'(\d+)\s*(?:min|minute|hour)', query_lower)
        if duration_match:
            duration = int(duration_match.group(1))
            if 'hour' in query_lower:
                duration *= 60
            max_duration = duration
        
        # Determine category
        if tech_skills and behavioral_skills:
            category = "mixed"
        elif tech_skills:
            category = "technical"
        elif behavioral_skills:
            category = "behavioral"
        else:
            category = "behavioral"  # Default
        
        return {
            "primary_role": "Professional",
            "technical_skills": tech_skills,
            "behavioral_skills": behavioral_skills,
            "duration_constraints": {
                "min_duration_minutes": min_duration,
                "max_duration_minutes": max_duration
            },
            "preferred_test_types": [],
            "query_category": category
        }
    
    def score_assessment_relevance(self, 
                                  query: str, 
                                  assessment_description: str,
                                  assessment_skills: List[str]) -> Dict[str, float]:
        """
        Use LLM to score how relevant an assessment is to a query
        
        Args:
            query: Job query
            assessment_description: Assessment description
            assessment_skills: List of assessment skills
            
        Returns:
            Dictionary with relevance scores
        """
        prompt = f"""
        Score how relevant this assessment is for the given job query.
        
        JOB QUERY: "{query}"
        
        ASSESSMENT:
        Description: {assessment_description}
        Skills: {', '.join(assessment_skills) if assessment_skills else 'Not specified'}
        
        Provide a JSON object with these scores (0.0 to 1.0):
        1. "skill_relevance": How well the assessment matches required skills
        2. "role_relevance": How appropriate for the job role
        3. "overall_relevance": Overall suitability
        
        Return ONLY the JSON object.
        Example:
        {{"skill_relevance": 0.8, "role_relevance": 0.7, "overall_relevance": 0.75}}
        """
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at matching assessments to job requirements."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=200
            )
            
            response_text = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"skill_relevance": 0.5, "role_relevance": 0.5, "overall_relevance": 0.5}
                
        except Exception as e:
            print(f"Error scoring relevance with Groq: {e}")
            return {"skill_relevance": 0.5, "role_relevance": 0.5, "overall_relevance": 0.5}