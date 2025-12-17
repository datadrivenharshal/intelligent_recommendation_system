import pandas as pd
import numpy as np
from typing import List, Dict
import json
from retrieval.rerank import RecommendationPipeline

def load_train_data(train_path='data/ground_truth/train_pairs.csv'):
    """Load training data with ground truth"""
    df = pd.read_csv(train_path)
    return df

def load_test_queries(test_path='data/ground_truth/test_queries.csv'):
    """Load test queries"""
    df = pd.read_csv(test_path)
    return df

def calculate_recall_at_k(recommended_urls: List[str], 
                         relevant_urls: List[str], 
                         k: int = 10) -> float:
    """Calculate Recall@K"""
    recommended_at_k = recommended_urls[:k]
    relevant_count = sum(1 for url in recommended_at_k if url in relevant_urls)
    total_relevant = len(relevant_urls)
    
    if total_relevant == 0:
        return 0.0
    
    return relevant_count / total_relevant

def evaluate_pipeline(pipeline, test_queries: Dict[str, List[str]], 
                     k: int = 10) -> Dict:
    """Evaluate pipeline on test queries"""
    results = []
    
    for query, relevant_urls in test_queries.items():
        # Get recommendations
        recommendations = pipeline.recommend(query, k=k)
        recommended_urls = [ass.url for ass in recommendations]
        
        # Calculate metrics
        recall = calculate_recall_at_k(recommended_urls, relevant_urls, k)
        
        results.append({
            'query': query,
            'recall@k': recall,
            'recommended_count': len(recommendations),
            'relevant_count': len(relevant_urls)
        })
    
    # Calculate mean metrics
    df = pd.DataFrame(results)
    mean_recall = df['recall@k'].mean()
    
    return {
        'mean_recall@k': mean_recall,
        'detailed_results': df,
        'total_queries': len(results)
    }

def generate_predictions(pipeline, test_queries_path: str, 
                        output_path: str = 'predictions.csv'):
    """Generate predictions for test set"""
    # Load test queries
    test_df = pd.read_csv(test_queries_path)
    
    predictions = []
    
    for _, row in test_df.iterrows():
        query = row['query']
        
        # Get recommendations
        recommendations = pipeline.recommend(query, k=10)
        recommended_urls = [ass.url for ass in recommendations]
        
        # Join URLs with comma
        predictions_str = ','.join(recommended_urls)
        
        predictions.append({
            'query': query,
            'predictions': predictions_str
        })
    
    # Save to CSV
    pred_df = pd.DataFrame(predictions)
    pred_df.to_csv(output_path, index=False)
    
    print(f"Predictions saved to {output_path}")
    print(f"Generated {len(pred_df)} predictions")
    
    return pred_df

if __name__ == '__main__':
    # Initialize pipeline
    print("Initializing recommendation pipeline...")
    pipeline = RecommendationPipeline()
    
    # Example evaluation with sample data
    print("\nEvaluating pipeline...")
    
    # Sample test queries (replace with actual data)
    test_queries = {
        "I need Java developers who can collaborate": [
            "https://www.shl.com/assessments/1",
            "https://www.shl.com/assessments/2"
        ],
        "Python developer with SQL skills": [
            "https://www.shl.com/assessments/3"
        ]
    }
    
    results = evaluate_pipeline(pipeline, test_queries, k=10)
    print(f"Mean Recall@10: {results['mean_recall@k']:.3f}")
    
    # Generate predictions for test set
    print("\nGenerating predictions...")
    predictions_df = generate_predictions(
        pipeline, 
        'data/ground_truth/test_queries.csv',
        'predictions.csv'
    )
    
    print("\nFirst few predictions:")
    print(predictions_df.head())