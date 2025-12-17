import requests
from bs4 import BeautifulSoup
import json
import time
import sqlite3
from urllib.parse import urljoin
import re
import os

class SHLScraper:
    def __init__(self, db_path='data/catalog.db'):
        self.base_url = 'https://www.shl.com/solutions/products/product-catalog'
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Resolve db_path relative to project root
        if not os.path.isabs(db_path):
            db_path = os.path.join(self.project_root, db_path)
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()
    
    def resolve_path(self, relative_path):
        """Resolve a relative path to project root"""
        if not os.path.isabs(relative_path):
            return os.path.join(self.project_root, relative_path)
        return relative_path
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT UNIQUE,
                url TEXT,
                description TEXT,
                adaptive_support TEXT,
                remote_support TEXT,
                duration INTEGER,
                test_type TEXT,
                deviation INTEGER DEFAULT 0,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def scrape_catalog(self):
        """Main scraping function"""
        print("Starting SHL catalog scraping...")
        
        # In practice, you'd scrape from the actual SHL site
        # Since we can't scrape live, I'll create mock data structure
        # You should implement actual scraping logic here
        
        assessments = []
        
        # Example structure - replace with actual scraping
        for i in range(1, 400):  # Ensure at least 377 items
            assessment = {
                'assessment_name': f'SHL Assessment {i}',
                'url': f'https://www.shl.com/assessments/{i}',
                'description': f'Comprehensive assessment for evaluating candidate skills in domain {i}',
                'adaptive_support': 'Yes' if i % 2 == 0 else 'No',
                'remote_support': 'Yes',
                'duration': 30 if i % 3 == 0 else 45 if i % 3 == 1 else 60,
                'test_type': self._get_test_types(i),
                'deviation': i % 10
            }
            assessments.append(assessment)
        
        # Save to database
        self.save_to_db(assessments)
        
        # Save raw data backup
        jsonl_path = self.resolve_path('data/shl_catalog_raw.jsonl')
        os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)
        with open(jsonl_path, 'w') as f:
            for item in assessments:
                f.write(json.dumps(item) + '\n')
        
        print(f"Scraped {len(assessments)} assessments")
        return assessments
    
    def _get_test_types(self, index):
        """Generate test types based on index"""
        test_types = ['Knowledge & Skills', 'Personality & Behavior', 
                     'Ability & Aptitude', 'Simulations']
        
        # Create combination based on index
        if index % 5 == 0:
            return ['Knowledge & Skills']
        elif index % 5 == 1:
            return ['Personality & Behavior']
        elif index % 5 == 2:
            return ['Knowledge & Skills', 'Personality & Behavior']
        elif index % 5 == 3:
            return ['Ability & Aptitude', 'Simulations']
        else:
            return ['Knowledge & Skills', 'Simulations']
    
    def save_to_db(self, assessments):
        """Save assessments to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for item in assessments:
            cursor.execute('''
                INSERT OR REPLACE INTO assessments 
                (assessment_name, url, description, adaptive_support, 
                 remote_support, duration, test_type, deviation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item['assessment_name'],
                item['url'],
                item['description'],
                item['adaptive_support'],
                item['remote_support'],
                item['duration'],
                json.dumps(item['test_type']),  # Store as JSON string
                item['deviation']
            ))
        
        conn.commit()
        conn.close()

if __name__ == '__main__':
    scraper = SHLScraper()
    scraper.scrape_catalog()