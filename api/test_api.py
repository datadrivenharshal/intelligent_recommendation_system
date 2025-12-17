# test_api.py
import requests
import json
import time

class APITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
    
    def test_health(self):
        """Test health endpoint"""
        print("Testing /health endpoint...")
        try:
            response = requests.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data['status']}")
                print(f"   Total assessments: {data['total_assessments']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_recommend(self, query):
        """Test recommendation endpoint"""
        print(f"\nTesting /recommend endpoint with query: '{query}'")
        try:
            payload = {"query": query}
            start_time = time.time()
            
            response = requests.post(
                f"{self.base_url}/recommend",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Recommendation successful in {elapsed:.2f}ms")
                print(f"   Query: {data['query']}")
                print(f"   Recommendations: {data['count']} assessments")
                
                # Validate response format
                if "recommended_assessments" in data:
                    assessments = data["recommended_assessments"]
                    if 5 <= len(assessments) <= 10:
                        print(f"✅ Correct number of assessments: {len(assessments)}")
                        
                        # Check first assessment format
                        if assessments:
                            first = assessments[0]
                            required_fields = ["url", "name", "adaptive_support", "description", 
                                            "duration", "remote_support", "test_type"]
                            missing = [field for field in required_fields if field not in first]
                            if not missing:
                                print("✅ Response format matches requirements")
                                print(f"   First assessment: {first['name']}")
                                print(f"   URL: {first['url']}")
                                print(f"   Duration: {first['duration']}min")
                                print(f"   Test types: {first['test_type']}")
                            else:
                                print(f"❌ Missing fields: {missing}")
                    else:
                        print(f"❌ Invalid number of assessments: {len(assessments)}")
                return True
            else:
                print(f"❌ Recommendation failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Recommendation error: {e}")
            return False
    
    def test_batch_recommend(self):
        """Test batch recommendation endpoint"""
        print("\nTesting /recommend/batch endpoint...")
        try:
            queries = [
                "Java developer with collaboration skills",
                "Sales professional",
                "Data analyst with SQL"
            ]
            
            response = requests.get(
                f"{self.base_url}/recommend/batch",
                params={"queries": ",".join(queries), "limit": 5}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Batch recommendation successful")
                print(f"   Total queries: {data['total_queries']}")
                print(f"   Successful: {data['successful_queries']}")
                
                for i, result in enumerate(data["batch_results"], 1):
                    if "error" not in result:
                        print(f"   Query {i}: '{result['query']}' - {result['count']} assessments")
                    else:
                        print(f"   Query {i}: ERROR - {result['error']}")
                return True
            else:
                print(f"❌ Batch recommendation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Batch recommendation error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all API tests"""
        print("=" * 60)
        print("Running API Tests")
        print("=" * 60)
        
        tests = [
            ("Health Check", lambda: self.test_health()),
            ("Single Recommendation - Java Developer", 
             lambda: self.test_recommend("Java developer who can collaborate with business teams, 40 minutes")),
            ("Single Recommendation - Sales", 
             lambda: self.test_recommend("Sales professional with communication skills")),
            ("Single Recommendation - Analyst", 
             lambda: self.test_recommend("Need cognitive and personality tests for analyst, 45 mins")),
            ("Batch Recommendations", lambda: self.test_batch_recommend()),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{test_name}")
            print("-" * 40)
            if test_func():
                passed += 1
        
        print("\n" + "=" * 60)
        print(f"Test Results: {passed}/{total} passed")
        
        if passed == total:
            print("✅ All tests passed! API is ready for submission.")
            return True
        else:
            print("⚠️  Some tests failed. Check the logs above.")
            return False

if __name__ == "__main__":
    # You can change the base_url if hosting elsewhere
    tester = APITester(base_url="http://localhost:8000")
    tester.run_all_tests()