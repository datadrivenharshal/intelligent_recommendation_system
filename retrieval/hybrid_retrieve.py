import numpy as np
import pickle
import os
import sys
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import faiss

# Ensure project root is on sys.path so local package imports work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from indexing.schema import Assessment

class HybridRetriever:
    def __init__(self, index_path='data/embeddings/faiss_index',
                 embedding_model='all-MiniLM-L6-v2'):
        # Resolve index_path relative to project root
        if not os.path.isabs(index_path):
            index_path = os.path.join(project_root, index_path)
        self.index_path = index_path

        self.embedding_model = SentenceTransformer(embedding_model)

        # Verify index files exist
        faiss_file = os.path.join(self.index_path, 'index.faiss')
        metadata_file = os.path.join(self.index_path, 'metadata.pkl')
        bm25_file = os.path.join(self.index_path, 'bm25.pkl')

        missing = [p for p in (faiss_file, metadata_file, bm25_file) if not os.path.exists(p)]
        if missing:
            raise RuntimeError(
                f"FAISS index files not found in '{self.index_path}'.\n"
                "Run the index builder to generate them: `python indexing/build_index.py`"
            )

        # Load FAISS index
        self.faiss_index = faiss.read_index(faiss_file)

        # Load metadata
        with open(metadata_file, 'rb') as f:
            self.metadata = pickle.load(f)

        # Load BM25 data
        with open(bm25_file, 'rb') as f:
            bm25_data = pickle.load(f)
        
        # Initialize BM25
        tokenized_texts = [text.lower().split() for text in bm25_data['texts']]
        self.bm25 = BM25Okapi(tokenized_texts)
        self.bm25_ids = bm25_data['ids']
        
        # Map ID to assessment
        self.id_to_assessment = {
            a['id']: Assessment(**a) for a in self.metadata['assessment_data']
        }
    
    def search(self, query: str, k: int = 20) -> List[Tuple[Assessment, float]]:
        """Hybrid search combining BM25 and FAISS"""
        
        # FAISS semantic search
        faiss_results = self._faiss_search(query, k * 2)
        
        # BM25 keyword search
        bm25_results = self._bm25_search(query, k * 2)
        
        # Combine scores
        combined_scores = self._combine_scores(faiss_results, bm25_results)
        
        # Get top k results
        top_k = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        
        results = []
        for assessment_id, score in top_k:
            if assessment_id in self.id_to_assessment:
                results.append((self.id_to_assessment[assessment_id], score))
        
        return results

    def retrieve(self,
                 query: str,
                 k: int = 20,
                 min_duration: int = None,
                 max_duration: int = None,
                 test_types: List[str] = None) -> List[Tuple[Assessment, float]]:
        """Retrieve candidates applying optional filters.

        Args:
            query: search query
            k: number of candidates to return
            min_duration: minimum duration in minutes
            max_duration: maximum duration in minutes
            test_types: list of preferred test types to filter by

        Returns:
            List of (Assessment, score) tuples
        """
        # Get initial candidates from hybrid search (request more to allow filtering)
        raw_k = max(k * 3, k + 10)
        results = self.search(query, raw_k)

        # Apply filters
        filtered = []
        for assessment, score in results:
            if min_duration is not None and assessment.duration is not None:
                if assessment.duration < min_duration:
                    continue
            if max_duration is not None and assessment.duration is not None:
                if assessment.duration > max_duration:
                    continue

            if test_types:
                # check for intersection
                if not set(a.lower() for a in assessment.test_type) & set(t.lower() for t in test_types):
                    continue

            filtered.append((assessment, score))
            if len(filtered) >= k:
                break

        return filtered
    
    def _faiss_search(self, query: str, k: int) -> Dict[int, float]:
        """Semantic search using FAISS"""
        query_embedding = self.embedding_model.encode([query])
        distances, indices = self.faiss_index.search(query_embedding.astype('float32'), k)
        
        results = {}
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata['assessment_ids']):
                assessment_id = self.metadata['assessment_ids'][idx]
                # Convert distance to similarity score (higher is better)
                score = 1.0 / (1.0 + distances[0][i])
                results[assessment_id] = score
        
        return results
    
    def _bm25_search(self, query: str, k: int) -> Dict[int, float]:
        """Keyword search using BM25"""
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Get top k indices
        top_indices = np.argsort(bm25_scores)[::-1][:k]
        
        results = {}
        for idx in top_indices:
            if idx < len(self.bm25_ids):
                assessment_id = self.bm25_ids[idx]
                # Normalize BM25 score to 0-1 range
                score = (bm25_scores[idx] - np.min(bm25_scores)) / \
                       (np.max(bm25_scores) - np.min(bm25_scores) + 1e-8)
                results[assessment_id] = score
        
        return results
    
    def _combine_scores(self, faiss_scores: Dict[int, float], 
                        bm25_scores: Dict[int, float]) -> Dict[int, float]:
        """Combine FAISS and BM25 scores with weights"""
        combined = {}
        all_ids = set(faiss_scores.keys()) | set(bm25_scores.keys())
        
        for assessment_id in all_ids:
            faiss_score = faiss_scores.get(assessment_id, 0)
            bm25_score = bm25_scores.get(assessment_id, 0)
            
            # Weighted combination (tune these weights based on evaluation)
            combined_score = 0.6 * faiss_score + 0.4 * bm25_score
            combined[assessment_id] = combined_score
        
        return combined