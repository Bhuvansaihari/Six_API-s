import requests
import time

BASE_URL = "http://localhost:8000"
WEBHOOK_ENDPOINT = f"{BASE_URL}/webhook/cand-job-matching"

# Update with valid IDs
TEST_CAND_ID = 2928
TEST_REQUIREMENT_ID = "1001"

def test_single_webhook():
    """Test a single webhook request"""
    payload = {
        "type": "INSERT",
        "table": "cand_job_matching",
        "record": {
            "matching_id": 1,
            "cand_id": TEST_CAND_ID,
            "requirement_id": TEST_REQUIREMENT_ID,
            "similarity_score": 0.85,
            "match_reason": "Test match",
            "matched_skills": ["Python", "FastAPI", "SQL"],
            "matched_at": "2025-01-20T10:00:00Z",
            "is_active": True
        },
        "old_record": None
    }
    
    print(f"Testing webhook endpoint: {WEBHOOK_ENDPOINT}")
    start_time = time.time()
    
    try:
        response = requests.post(WEBHOOK_ENDPOINT, json=payload, timeout=60)
        response_time = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {response_time:.3f}s")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✓ Test PASSED")
            else:
                print(f"⚠ Test returned success=False: {data.get('message')}")
        else:
            print(f"✗ Test FAILED: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"✗ Test ERROR: {str(e)}")

if __name__ == "__main__":
    test_single_webhook()

