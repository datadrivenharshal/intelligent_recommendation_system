from pydantic import BaseModel
from typing import List, Optional
import json

class Assessment(BaseModel):
    id: int
    assessment_name: str
    url: str
    description: str
    adaptive_support: str  # "Yes" or "No"
    remote_support: str    # "Yes" or "No"
    duration: int          # minutes
    test_type: List[str]
    skills: Optional[List[str]] = None
    deviation: int = 0
    
    @classmethod
    def from_db_row(cls, row):
        """Create Assessment from database row"""
        return cls(
            id=row[0],
            assessment_name=row[1],
            url=row[2],
            description=row[3],
            adaptive_support=row[4],
            remote_support=row[5],
            duration=row[6],
            test_type=json.loads(row[7]) if row[7] else [],
            skills=None,
            deviation=row[8] if len(row) > 8 else 0
        )

class QueryRequest(BaseModel):
    query: str

class RecommendationResponse(BaseModel):
    recommended_assessments: List[Assessment]