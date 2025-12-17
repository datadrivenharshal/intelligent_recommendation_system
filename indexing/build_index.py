import sqlite3
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle
import os
import sys

# Ensure project root is on sys.path so local package imports work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from tqdm import tqdm
from indexing.schema import Assessment

class IndexBuilder:
    def __init__(self, db_path='data/catalog.db', 
                 embedding_model='all-MiniLM-L6-v2'):
        # Resolve paths relative to project root
        if not os.path.isabs(db_path):
            db_path = os.path.join(project_root, db_path)
        self.db_path = db_path
        # Ensure DB directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.embedding_model = SentenceTransformer(embedding_model)
        # Resolve index path to project data folder
        self.index_path = os.path.join(project_root, 'data', 'embeddings', 'faiss_index')
        os.makedirs(self.index_path, exist_ok=True)
        
    def load_assessments(self):
        """Load assessments from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assessments')
        rows = cursor.fetchall()
        conn.close()
        
        assessments = []
        for row in rows:
            try:
                assessment = Assessment.from_db_row(row)
                assessments.append(assessment)
            except Exception as e:
                print(f"Error loading row {row[0]}: {e}")
        
        print(f"Loaded {len(assessments)} assessments")
        return assessments
    
    def create_text_for_embedding(self, assessment: Assessment) -> str:
        """Create text representation for embedding"""
        text_parts = [
            assessment.assessment_name,
            assessment.description,
            f"Test types: {', '.join(assessment.test_type)}",
            f"Duration: {assessment.duration} minutes",
            f"Adaptive: {assessment.adaptive_support}",
            f"Remote: {assessment.remote_support}"
        ]
        return ". ".join(text_parts)
    
    def build_faiss_index(self, assessments):
        """Build FAISS index from assessments"""
        os.makedirs(self.index_path, exist_ok=True)
        
        # Generate embeddings
        texts = [self.create_text_for_embedding(a) for a in assessments]
        print("Generating embeddings...")
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
        
        # Build FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype('float32'))
        
        # Save index and metadata
        faiss.write_index(index, os.path.join(self.index_path, 'index.faiss'))
        
        # Save metadata
        metadata = {
            'assessment_ids': [a.id for a in assessments],
            'texts': texts,
            'assessment_data': [a.dict() for a in assessments]
        }
        
        with open(os.path.join(self.index_path, 'metadata.pkl'), 'wb') as f:
            pickle.dump(metadata, f)
        
        print(f"Built FAISS index with {len(assessments)} items")
        return index, metadata
    
    def build_bm25_index(self, assessments):
        """Build BM25 index (simplified - use actual BM25 in production)"""
        # For simplicity, store texts for BM25 calculation
        texts = [self.create_text_for_embedding(a) for a in assessments]
        ids = [a.id for a in assessments]
        
        bm25_data = {
            'texts': texts,
            'ids': ids
        }
        
        with open(os.path.join(self.index_path, 'bm25.pkl'), 'wb') as f:
            pickle.dump(bm25_data, f)
        
        return bm25_data
    
    def build_all(self):
        """Build all indices"""
        print("Building indices...")
        assessments = self.load_assessments()
        
        # Build FAISS index
        faiss_index, metadata = self.build_faiss_index(assessments)
        
        # Build BM25 index
        bm25_data = self.build_bm25_index(assessments)
        
        print("Indices built successfully!")
        return faiss_index, metadata, bm25_data

if __name__ == '__main__':
    builder = IndexBuilder()
    builder.build_all()