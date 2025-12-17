# run_api.py
#!/usr/bin/env python3
"""
Start the SHL Assessment Recommendation API
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.main import start_server

if __name__ == "__main__":
    print("=" * 60)
    print("SHL Assessment Recommendation System")
    print("=" * 60)
    
    # Check if required files exist
    required_files = [
        "data/catalog.db",
        "data/embeddings/faiss_index.bin",
        "data/embeddings/metadata.pkl"
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"⚠️  Warning: {file} not found")
            print("   Run 'python indexing/build_index.py' first")
    
    # Check for Groq API key
    if not os.getenv("GROQ_API_KEY"):
        print("⚠️  GROQ_API_KEY not set. LLM features will be disabled.")
        print("   Set it with: export GROQ_API_KEY='your_key'")
        print("   Or add to .env file")
    
    print("\n" + "=" * 60)
    
    # Start the server
    start_server()