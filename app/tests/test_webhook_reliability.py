import asyncio
import aiohttp
import time
import json
from typing import List, Dict, Tuple
from datetime import datetime
import statistics

# Configuration
BASE_URL = "http://localhost:8000"
WEBHOOK_ENDPOINT = f"{BASE_URL}/webhook/cand-job-matching"
HEALTH_ENDPOINT = f"{BASE_URL}/health"

# Test data - Update these with valid IDs from your database
TEST_CAND_ID = 2928  # Replace with valid cand_id
TEST_REQUIREMENT_ID = "1001"  # Replace with valid requirement_id


class TestResults:
    """Track test results"""
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.skipped_requests = 0
        self.response_times = []
        self.errors = []
        self.start_time = None
        self.end_time = None
    
    def add_result(self, success: bool, response_time: float, error: str = None, skipped: bool = False):
        self.total_requests += 1
        if skipped:
            self.skipped_requests += 1
        elif success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error:
                self.errors.append(error)
        self.response_times.append(response_time)
    
    def print_summary(self):
        duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Requests: {self.total_requests}")
        print(f"Successful: {self.successful_requests} ({self.successful_requests/self.total_requests*100:.1f}%)")
        print(f"Failed: {self.failed_requests} ({self.failed_requests/self.total_requests*100:.1f}%)")
        print(f"Skipped: {self.skipped_requests} ({self.skipped_requests/self.total_requests*100:.1f}%)")
        print(f"Total Duration: {duration:.2f} seconds")
        print(f"Requests/Second: {self.total_requests/duration:.2f}" if duration > 0 else "N/A")
        
        if self.response_times:
            print(f"\nResponse Time Statistics:")
            print(f"  Min: {min(self.response_times):.3f}s")
            print(f"  Max: {max(self.response_times):.3f}s")
            print(f"  Mean: {statistics.mean(self.response_times):.3f}s")
            print(f"  Median: {statistics.median(self.response_times):.3f}s")
            if len(self.response_times) > 1:
                print(f"  Std Dev: {statistics.stdev(self.response_times):.3f}s")
            print(f"  95th Percentile: {self._percentile(95):.3f}s")
            print(f"  99th Percentile: {self._percentile(99):.3f}s")
        
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            error_counts = {}
            for error in self.errors[:10]:  # Show first 10 errors
                error_key = error[:100]  # Truncate long errors
                error_counts[error_key] = error_counts.get(error_key, 0) + 1
            for error, count in list(error_counts.items())[:5]:
                print(f"  {count}x: {error}")
    
    def _percentile(self, p: float) -> float:
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * p / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]


def create_webhook_payload(
    matching_id: int,
    cand_id: int,
    requirement_id: str,
    similarity_score: float,
    match_reason: str = "Test match"
) -> dict:
    """Create a webhook payload for testing"""
    return {
        "type": "INSERT",
        "table": "cand_job_matching",
        "record": {
            "matching_id": matching_id,
            "cand_id": cand_id,
            "requirement_id": requirement_id,
            "similarity_score": similarity_score,
            "match_reason": match_reason,
            "matched_skills": ["Python", "FastAPI", "SQL"],
            "matched_at": datetime.now().isoformat() + "Z",
            "is_active": True
        },
        "old_record": None
    }


async def send_webhook(session: aiohttp.ClientSession, payload: dict) -> Tuple[bool, float, dict, str]:
    """Send a single webhook request"""
    start_time = time.time()
    try:
        async with session.post(
            WEBHOOK_ENDPOINT,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            response_time = time.time() - start_time
            response_data = await response.json()
            
            if response.status == 200:
                success = response_data.get("success", False)
                skipped = "below threshold" in response_data.get("message", "").lower()
                return success, response_time, response_data, None
            else:
                return False, response_time, response_data, f"HTTP {response.status}"
    
    except asyncio.TimeoutError:
        response_time = time.time() - start_time
        return False, response_time, {}, "Timeout"
    except Exception as e:
        response_time = time.time() - start_time
        return False, response_time, {}, str(e)


async def test_concurrent_requests(num_requests: int, concurrency: int, results: TestResults):
    """Test concurrent webhook requests"""
    print(f"\nTesting {num_requests} requests with concurrency={concurrency}...")
    
    payload = create_webhook_payload(
        matching_id=1,
        cand_id=TEST_CAND_ID,
        requirement_id=TEST_REQUIREMENT_ID,
        similarity_score=0.85
    )
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def send_with_semaphore(session, payload, request_id):
        async with semaphore:
            success, response_time, data, error = await send_webhook(session, payload)
            skipped = "below threshold" in data.get("message", "").lower() if data else False
            results.add_result(success, response_time, error, skipped)
            if request_id % 10 == 0:
                print(f"  Completed {request_id}/{num_requests} requests...")
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            send_with_semaphore(session, payload, i+1)
            for i in range(num_requests)
        ]
        await asyncio.gather(*tasks)


async def test_different_scenarios(results: TestResults):
    """Test different webhook scenarios"""
    print("\nTesting different scenarios...")
    
    scenarios = [
        {
            "name": "High similarity score (0.85)",
            "payload": create_webhook_payload(1, TEST_CAND_ID, TEST_REQUIREMENT_ID, 0.85),
            "expected_success": True
        },
        {
            "name": "Low similarity score (0.65) - should skip",
            "payload": create_webhook_payload(2, TEST_CAND_ID, TEST_REQUIREMENT_ID, 0.65),
            "expected_success": False  # Should skip due to low score
        },
        {
            "name": "Very high similarity (0.95)",
            "payload": create_webhook_payload(3, TEST_CAND_ID, TEST_REQUIREMENT_ID, 0.95),
            "expected_success": True
        },
        {
            "name": "Threshold similarity (0.70)",
            "payload": create_webhook_payload(4, TEST_CAND_ID, TEST_REQUIREMENT_ID, 0.70),
            "expected_success": True
        },
        {
            "name": "Just below threshold (0.69)",
            "payload": create_webhook_payload(5, TEST_CAND_ID, TEST_REQUIREMENT_ID, 0.69),
            "expected_success": False  # Should skip
        },
    ]
    
    async with aiohttp.ClientSession() as session:
        for scenario in scenarios:
            print(f"  Testing: {scenario['name']}")
            success, response_time, data, error = await send_webhook(session, scenario["payload"])
            skipped = "below threshold" in data.get("message", "").lower() if data else False
            results.add_result(success, response_time, error, skipped)
            
            if scenario["expected_success"]:
                if success:
                    print(f"    ✓ Passed (success={success}, time={response_time:.3f}s)")
                else:
                    print(f"    ✗ Failed (expected success, got success={success})")
            else:
                if skipped or not success:
                    print(f"    ✓ Passed (correctly skipped/failed, time={response_time:.3f}s)")
                else:
                    print(f"    ✗ Failed (expected skip/fail, got success={success})")
            await asyncio.sleep(0.5)  # Small delay between requests


async def test_health_endpoint():
    """Test health check endpoint"""
    print("\nTesting health endpoint...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HEALTH_ENDPOINT) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"  ✓ Health check passed: {data}")
                    return True
                else:
                    print(f"  ✗ Health check failed: HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"  ✗ Health check error: {str(e)}")
        return False


async def test_burst_load(num_requests: int, results: TestResults):
    """Test burst load (all requests at once)"""
    print(f"\nTesting burst load with {num_requests} simultaneous requests...")
    
    payload = create_webhook_payload(
        matching_id=1,
        cand_id=TEST_CAND_ID,
        requirement_id=TEST_REQUIREMENT_ID,
        similarity_score=0.85
    )
    
    async with aiohttp.ClientSession() as session:
        tasks = [send_webhook(session, payload) for _ in range(num_requests)]
        results_batch = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results_batch:
            if isinstance(result, Exception):
                results.add_result(False, 0, str(result))
            else:
                success, response_time, data, error = result
                skipped = "below threshold" in data.get("message", "").lower() if data else False
                results.add_result(success, response_time, error, skipped)


async def test_sustained_load(duration_seconds: int, requests_per_second: int, results: TestResults):
    """Test sustained load over time"""
    print(f"\nTesting sustained load: {requests_per_second} req/s for {duration_seconds} seconds...")
    
    payload = create_webhook_payload(
        matching_id=1,
        cand_id=TEST_CAND_ID,
        requirement_id=TEST_REQUIREMENT_ID,
        similarity_score=0.85
    )
    
    start_time = time.time()
    request_count = 0
    interval = 1.0 / requests_per_second
    
    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration_seconds:
            request_start = time.time()
            success, response_time, data, error = await send_webhook(session, payload)
            skipped = "below threshold" in data.get("message", "").lower() if data else False
            results.add_result(success, response_time, error, skipped)
            request_count += 1
            
            # Rate limiting
            elapsed = time.time() - request_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)


async def main():
    """Run all tests"""
    print("="*60)
    print("WEBHOOK API RELIABILITY TEST SUITE")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Candidate ID: {TEST_CAND_ID}")
    print(f"Test Requirement ID: {TEST_REQUIREMENT_ID}")
    print("\n⚠️  Make sure to update TEST_CAND_ID and TEST_REQUIREMENT_ID")
    print("   with valid IDs from your database!")
    print("="*60)
    
    # Check health first
    health_ok = await test_health_endpoint()
    if not health_ok:
        print("\n❌ Health check failed. Is the server running?")
        return
    
    results = TestResults()
    results.start_time = time.time()
    
    try:
        # Test 1: Different scenarios
        await test_different_scenarios(results)
        
        # Test 2: Concurrent requests (moderate load)
        await test_concurrent_requests(num_requests=50, concurrency=10, results=results)
        
        # Test 3: Burst load
        await test_burst_load(num_requests=20, results=results)
        
        # Test 4: Sustained load
        await test_sustained_load(duration_seconds=10, requests_per_second=5, results=results)
        
        # Test 5: High concurrency test
        print(f"\nTesting high concurrency (100 requests, 20 concurrent)...")
        await test_concurrent_requests(num_requests=100, concurrency=20, results=results)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        results.end_time = time.time()
        results.print_summary()
        
        # Performance assessment
        print("\n" + "="*60)
        print("PERFORMANCE ASSESSMENT")
        print("="*60)
        success_rate = results.successful_requests / results.total_requests * 100 if results.total_requests > 0 else 0
        avg_response_time = statistics.mean(results.response_times) if results.response_times else 0
        
        if success_rate >= 95 and avg_response_time < 2.0:
            print("✓ EXCELLENT: High success rate and fast response times")
        elif success_rate >= 90 and avg_response_time < 3.0:
            print("✓ GOOD: Acceptable success rate and response times")
        elif success_rate >= 80:
            print("⚠ WARNING: Success rate could be improved")
        else:
            print("✗ CRITICAL: Low success rate - needs investigation")
        
        if avg_response_time > 5.0:
            print("⚠ WARNING: Response times are high - consider optimization")


if __name__ == "__main__":
    # Install required package: pip install aiohttp
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted")

