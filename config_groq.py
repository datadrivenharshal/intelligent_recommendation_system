# config.py - Add API configuration
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings"""
    # LLM Settings
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-70b-8192")
    
    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_DEBUG: bool = os.getenv("API_DEBUG", "True").lower() == "true"
    
    # Retrieval Settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    TOP_K_RETRIEVE: int = 20
    TOP_K_FINAL: int = 10
    MIN_RECOMMENDATIONS: int = 5
    MAX_RECOMMENDATIONS: int = 10
    
    # Paths
    FAISS_INDEX_PATH: str = "data/embeddings/faiss_index.bin"
    METADATA_PATH: str = "data/embeddings/metadata.pkl"
    DB_PATH: str = "data/catalog.db"
    
    # Test Type Categories
    TECHNICAL_TYPES = ["Knowledge & Skills", "Ability & Aptitude", "Simulations"]
    BEHAVIORAL_TYPES = ["Personality & Behavior", "Competencies", "Biodata & Situational Judgement"]
    
    # Balance Settings
    MIN_TECHNICAL_PCT: float = 0.3
    MIN_BEHAVIORAL_PCT: float = 0.3

config = Config()