"""
Load testing script for webhook endpoint

This script sends multiple concurrent webhook requests to test
the Celery + Redis implementation's capacity.

Usage:
    python scripts/test_webhook_load.py
"""
import asyncio
import httpx
import time
from typing import Tuple, List


async def send_webhook(
    client: httpx.AsyncClient,
    cand_id: int,
    req_id: int
) -> Tuple[int, float]:
    """
    Send a single webhook request
    
    Args:
        client: HTTP client
        cand_id: Candidate ID
        req_id: Requirement ID
        
    Returns:
        Tuple of (status_code, duration_seconds)
    """
    payload = {
        "type": "INSERT",
        "table": "cand_job_matching",
        "record": {
            "matching_id": cand_id,
            "cand_id": cand_id,
            "requirement_id": req_id,
            "similarity_score": 0.85,
            "match_reason": "Load test",
            "matched_skills": ["Python", "FastAPI"],
            "matched_at": "2025-01-18T12:00:00Z",
            "is_active": True
        }
    }
    
    start = time.time()
    try:
        response = await client.post(
            "http://localhost:8000/webhook/cand-job-matching",
            json=payload
        )
        duration = time.time() - start
        return response.status_code, duration
    except Exception as e:
        duration = time.time() - start
        print(f"Error: {str(e)}")
        return 0, duration


async def load_test(num_requests: int = 100):
    """
    Run load test with specified number of concurrent requests
    
    Args:
        num_requests: Number of concurrent webhook requests to send
    """
    print(f"\n{'='*60}")
    print(f"🚀 Webhook Load Test - {num_requests} Concurrent Requests")
    print(f"{'='*60}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create tasks
        tasks = [
            send_webhook(client, 2900 + i, 1000 + i)
            for i in range(num_requests)
        ]
        
        # Execute all requests concurrently
        print(f"⏳ Sending {num_requests} requests...")
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        success_count = sum(1 for code, _ in results if code == 202)
        error_count = sum(1 for code, _ in results if code == 0)
        other_count = sum(1 for code, _ in results if code not in [0, 202])
        
        durations = [d for _, d in results if d > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        # Print results
        print(f"\n{'='*60}")
        print(f"📊 Results")
        print(f"{'='*60}\n")
        
        print(f"✅ Success (202):     {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
        print(f"❌ Errors:            {error_count}/{num_requests}")
        print(f"⚠️  Other Status:      {other_count}/{num_requests}")
        
        print(f"\n{'='*60}")
        print(f"⏱️  Performance Metrics")
        print(f"{'='*60}\n")
        
        print(f"Total Time:           {total_time:.2f}s")
        print(f"Average Response:     {avg_duration*1000:.2f}ms")
        print(f"Min Response:         {min_duration*1000:.2f}ms")
        print(f"Max Response:         {max_duration*1000:.2f}ms")
        print(f"Throughput:           {num_requests/total_time:.2f} req/sec")
        
        # Verdict
        print(f"\n{'='*60}")
        if success_count == num_requests and avg_duration < 0.1:
            print(f"✅ PASS: All requests succeeded with <100ms response time")
        elif success_count >= num_requests * 0.95:
            print(f"⚠️  PARTIAL: >95% success rate, but some failures")
        else:
            print(f"❌ FAIL: Success rate below 95%")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    # Run tests with different loads
    asyncio.run(load_test(10))    # Warm-up
    asyncio.run(load_test(100))   # Target load
    asyncio.run(load_test(200))   # Stress test
