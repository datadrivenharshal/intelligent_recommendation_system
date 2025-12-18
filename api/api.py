# api/main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
import json
from datetime import datetime
import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from indexing.schema import Assessment
from retrieval.rerank_groq import GroqReranker

# Initialize FastAPI app
app = FastAPI(
    title="SHL Assessment Recommendation API",
    description="API for recommending SHL assessments based on job descriptions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize recommendation engine
recommender = None

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., example="healthy")
    timestamp: str = Field(..., example="2024-01-01T12:00:00Z")
    version: str = Field(..., example="1.0.0")
    total_assessments: int = Field(..., example=399)

class RecommendationRequest(BaseModel):
    """Request model for assessment recommendations"""
    query: str = Field(..., min_length=1, max_length=5000, 
                      example="Java developer who can collaborate with business teams")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Java developer who can collaborate with business teams"
            }
        }

class AssessmentResponse(BaseModel):
    """Assessment response model matching requirements"""
    url: str = Field(..., example="https://www.shl.com/solutions/products/product-catalog/view/java-8-new/")
    name: str = Field(..., example="Java 8 Assessment")
    adaptive_support: str = Field(..., example="Yes")
    description: str = Field(..., example="Comprehensive Java 8 assessment")
    duration: int = Field(..., example=45)
    remote_support: str = Field(..., example="Yes")
    test_type: List[str] = Field(..., example=["Knowledge & Skills"])
    deviation: int = Field(..., example=0)
    
    class Config:
        schema_extra = {
            "example": {
                "url": "https://www.shl.com/solutions/products/product-catalog/view/java-8-new/",
                "name": "Java 8 Assessment",
                "adaptive_support": "Yes",
                "description": "Comprehensive Java 8 assessment for evaluating candidate skills",
                "duration": 45,
                "remote_support": "Yes",
                "test_type": ["Knowledge & Skills"],
                "deviation": 0
            }
        }

class RecommendationResponse(BaseModel):
    """Response model for recommendations"""
    query: str = Field(..., example="Java developer with collaboration skills")
    recommended_assessments: List[AssessmentResponse] = Field(...)
    count: int = Field(..., example=5)
    processing_time_ms: float = Field(..., example=125.5)
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Java developer with collaboration skills",
                "recommended_assessments": [],
                "count": 5,
                "processing_time_ms": 125.5
            }
        }

@app.on_event("startup")
async def startup_event():
    """Initialize recommendation engine on startup"""
    global recommender
    try:
        recommender = GroqReranker(use_llm=True)
        print(f"✅ Recommendation engine initialized successfully")
        print(f"📊 Total assessments loaded: {get_assessment_count()}")
    except Exception as e:
        print(f"⚠️  Failed to initialize recommender: {e}")
        # Fallback to rule-based
        recommender = GroqReranker(use_llm=False)
        print("✅ Using rule-based recommendation engine")

def get_assessment_count() -> int:
    """Get total number of assessments in database"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM assessments")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 399  # Fallback to mock data count

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Health status of the API
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        version="1.0.0",
        total_assessments=get_assessment_count()
    )

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_assessments(request: RecommendationRequest):
    """
    Recommend SHL assessments based on job description
    
    Args:
        request: Contains the query/job description
        
    Returns:
        List of recommended assessments (5-10 items)
    """
    import time
    start_time = time.time()
    
    try:
        # Validate query
        if not request.query or len(request.query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        query = request.query.strip()
        
        # Get recommendations
        if not recommender:
            raise HTTPException(status_code=500, detail="Recommendation engine not initialized")
        
        assessments = recommender.recommend(
            query=query,
            k=config.MAX_RECOMMENDATIONS
        )
        
        # Ensure we have at least 5 recommendations
        if len(assessments) < config.MIN_RECOMMENDATIONS:
            # Get more from database as fallback
            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, assessment_name, url, description, 
                       adaptive_support, remote_support, duration, 
                       test_type, deviation
                FROM assessments 
                LIMIT ?
            """, (config.MIN_RECOMMENDATIONS - len(assessments),))
            
            for row in cursor.fetchall():
                try:
                    fallback_assess = Assessment.from_db_row(row)
                    if fallback_assess not in assessments:
                        assessments.append(fallback_assess)
                except:
                    pass
            
            conn.close()
        
        # Convert to response format
        recommended_assessments = []
        for assessment in assessments[:config.MAX_RECOMMENDATIONS]:
            # Parse test_type from JSON string if needed
            if isinstance(assessment.test_type, str):
                try:
                    test_types = json.loads(assessment.test_type)
                except:
                    test_types = [assessment.test_type]
            else:
                test_types = assessment.test_type
            
            response_item = AssessmentResponse(
                url=assessment.url,
                name=assessment.assessment_name,
                adaptive_support=assessment.adaptive_support,
                description=assessment.description[:500] if len(assessment.description) > 500 else assessment.description,
                duration=assessment.duration,
                remote_support=assessment.remote_support,
                test_type=test_types,
                deviation=assessment.deviation or 0
            )
            recommended_assessments.append(response_item)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return RecommendationResponse(
            query=query,
            recommended_assessments=recommended_assessments,
            count=len(recommended_assessments),
            processing_time_ms=round(processing_time_ms, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/recommend/batch")
async def batch_recommend(
    queries: str = Query(..., description="Comma-separated list of queries"),
    limit: int = Query(10, ge=1, le=10, description="Max assessments per query")
):
    """
    Batch recommendation endpoint for multiple queries
    
    Args:
        queries: Comma-separated list of queries
        limit: Max assessments per query (1-10)
        
    Returns:
        Recommendations for each query
    """
    query_list = [q.strip() for q in queries.split(",") if q.strip()]
    
    if not query_list:
        raise HTTPException(status_code=400, detail="No valid queries provided")
    
    results = []
    for query in query_list:
        try:
            request = RecommendationRequest(query=query)
            response = await recommend_assessments(request)
            results.append({
                "query": query,
                "recommendations": response.recommended_assessments[:limit],
                "count": min(len(response.recommended_assessments), limit)
            })
        except Exception as e:
            results.append({
                "query": query,
                "error": str(e),
                "recommendations": [],
                "count": 0
            })
    
    return {
        "batch_results": results,
        "total_queries": len(query_list),
        "successful_queries": sum(1 for r in results if not r.get("error"))
    }

@app.get("/assessments/search")
async def search_assessments(
    keyword: Optional[str] = Query(None, description="Search keyword"),
    min_duration: Optional[int] = Query(None, ge=1, le=240, description="Minimum duration in minutes"),
    max_duration: Optional[int] = Query(None, ge=1, le=240, description="Maximum duration in minutes"),
    test_type: Optional[str] = Query(None, description="Test type filter"),
    limit: int = Query(20, ge=1, le=100, description="Max results")
):
    """
    Direct search endpoint for assessments
    
    Args:
        keyword: Search keyword
        min_duration: Minimum duration
        max_duration: Maximum duration
        test_type: Test type filter
        limit: Max results
        
    Returns:
        Filtered assessments
    """
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        
        query = "SELECT id, assessment_name, url, description, adaptive_support, remote_support, duration, test_type, deviation FROM assessments WHERE 1=1"
        params = []
        
        if keyword:
            query += " AND (assessment_name LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        if min_duration:
            query += " AND duration >= ?"
            params.append(min_duration)
        
        if max_duration:
            query += " AND duration <= ?"
            params.append(max_duration)
        
        if test_type:
            query += " AND test_type LIKE ?"
            params.append(f"%{test_type}%")
        
        query += " LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        assessments = []
        for row in rows:
            try:
                assess = Assessment.from_db_row(row)
                
                # Parse test_type
                if isinstance(assess.test_type, str):
                    try:
                        test_types = json.loads(assess.test_type)
                    except:
                        test_types = [assess.test_type]
                else:
                    test_types = assess.test_type
                
                assessments.append({
                    "url": assess.url,
                    "name": assess.assessment_name,
                    "adaptive_support": assess.adaptive_support,
                    "description": assess.description[:300],
                    "duration": assess.duration,
                    "remote_support": assess.remote_support,
                    "test_type": test_types,
                    "deviation": assess.deviation or 0
                })
            except:
                continue
        
        return {
            "count": len(assessments),
            "assessments": assessments
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "SHL Assessment Recommendation API",
        "version": "1.0.0",
        "endpoints": {
            "GET /health": "Health check",
            "POST /recommend": "Get assessment recommendations",
            "GET /recommend/batch": "Batch recommendations",
            "GET /assessments/search": "Direct assessment search"
        },
        "documentation": "/docs"
    }

def start_server():
    """Start the FastAPI server"""
    print(f"🚀 Starting SHL Assessment Recommendation API")
    print(f"📡 Host: {config.API_HOST}")
    print(f"🔌 Port: {config.API_PORT}")
    print(f"🔧 Debug: {config.API_DEBUG}")
    print(f"📊 Assessments: {get_assessment_count()}")
    print(f"🌐 API Docs: http://{config.API_HOST}:{config.API_PORT}/docs")
    print(f"🏥 Health Check: http://{config.API_HOST}:{config.API_PORT}/health")
    
    uvicorn.run(
        "api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_DEBUG,
        log_level="info"
    )

if __name__ == "__main__":
    start_server()