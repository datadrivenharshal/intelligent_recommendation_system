from typing import List, Tuple
from indexing.schema import Assessment
import re

class RecommendationRules:
    @staticmethod
    def balance_knowledge_personality(assessments: List[Tuple[Assessment, float]], 
                                      query: str) -> List[Tuple[Assessment, float]]:
        """
        Balance Knowledge (K) and Personality (P) type assessments
        when query mentions both technical and behavioral skills
        """
        # Check if query mentions both technical and behavioral aspects
        technical_keywords = ['java', 'python', 'sql', 'code', 'programming', 
                             'technical', 'skill', 'knowledge', 'develop']
        behavioral_keywords = ['collaborat', 'team', 'stakeholder', 'behavior',
                              'personality', 'soft skill', 'communicat', 'lead']
        
        query_lower = query.lower()
        has_technical = any(keyword in query_lower for keyword in technical_keywords)
        has_behavioral = any(keyword in query_lower for keyword in behavioral_keywords)
        
        if not (has_technical and has_behavioral):
            return assessments
        
        # Separate K and P type assessments
        k_assessments = []
        p_assessments = []
        other_assessments = []
        
        for assessment, score in assessments:
            test_types = [t.lower() for t in assessment.test_type]
            
            if 'knowledge' in ' '.join(test_types) or 'skill' in ' '.join(test_types):
                k_assessments.append((assessment, score))
            elif 'personality' in ' '.join(test_types) or 'behavior' in ' '.join(test_types):
                p_assessments.append((assessment, score))
            else:
                other_assessments.append((assessment, score))
        
        # Balance: take equal number from K and P if possible
        balanced_results = []
        min_count = min(len(k_assessments), len(p_assessments), 3)
        
        # Add balanced K and P assessments
        for i in range(min_count):
            if i < len(k_assessments):
                balanced_results.append(k_assessments[i])
            if i < len(p_assessments):
                balanced_results.append(p_assessments[i])
        
        # Add remaining from original list
        added_ids = {a[0].id for a in balanced_results}
        for assessment, score in assessments:
            if assessment.id not in added_ids:
                balanced_results.append((assessment, score))
        
        return balanced_results[:10]  # Return top 10
    
    @staticmethod
    def filter_by_duration(assessments: List[Tuple[Assessment, float]], 
                          max_duration: int = 90) -> List[Tuple[Assessment, float]]:
        """Filter out assessments that are too long"""
        return [(a, s) for a, s in assessments if a.duration <= max_duration]
    
    @staticmethod
    def ensure_diversity(assessments: List[Tuple[Assessment, float]], 
                        top_k: int = 10) -> List[Tuple[Assessment, float]]:
        """Ensure diversity in test types"""
        if len(assessments) <= top_k:
            return assessments
        
        selected = []
        selected_types = set()
        
        for assessment, score in assessments:
            assessment_types = tuple(sorted(assessment.test_type))
            
            if assessment_types not in selected_types:
                selected.append((assessment, score))
                selected_types.add(assessment_types)
            
            if len(selected) >= top_k:
                break
        
        # If we don't have enough diverse items, add highest scoring ones
        if len(selected) < top_k:
            for assessment, score in assessments:
                if (assessment, score) not in selected:
                    selected.append((assessment, score))
                if len(selected) >= top_k:
                    break
        
        return selected