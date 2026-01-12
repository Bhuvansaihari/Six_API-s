"""
Test script for daily application limit feature.

This script tests the daily limit functionality with various scenarios.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.auto_apply_preferences import (
    get_candidate_preferences,
    check_daily_limit_reached,
    get_todays_application_count,
    create_default_preferences,
    check_existing_application
)


async def test_preferences_service():
    """Test the preferences service functions."""
    print("=" * 60)
    print("Testing Daily Application Limit Feature")
    print("=" * 60)
    
    # Test candidate ID (use a real one from your database)
    test_cand_id = 3044
    test_requirement_id = "130130"
    
    print(f"\n[Test 1: Get Candidate Preferences]")
    print(f"Testing with cand_id={test_cand_id}")
    
    try:
        preferences = await get_candidate_preferences(test_cand_id)
        print(f"[SUCCESS] Retrieved preferences:")
        print(f"  Daily Limit: {preferences.get('daily_application_limit', 'N/A')}")
        print(f"  Is Active: {preferences.get('is_active', 'N/A')}")
        print(f"  Apply Recent First: {preferences.get('apply_most_recent_jobs_first', 'N/A')}")
    except Exception as e:
        print(f"[ERROR] Failed to get preferences: {e}")
        return
    
    print(f"\n[Test 2: Count Today's Applications]")
    try:
        count = await get_todays_application_count(test_cand_id)
        print(f"[SUCCESS] Applications today: {count}")
    except Exception as e:
        print(f"[ERROR] Failed to count applications: {e}")
        return
    
    print(f"\n[Test 3: Check Daily Limit]")
    try:
        daily_limit = preferences.get('daily_application_limit', 10)
        limit_reached, applications_today = await check_daily_limit_reached(
            test_cand_id,
            daily_limit
        )
        print(f"[SUCCESS] Daily limit check:")
        print(f"  Applications today: {applications_today}")
        print(f"  Daily limit: {daily_limit}")
        print(f"  Limit reached: {limit_reached}")
        
        if limit_reached:
            print(f"  [WARNING] Candidate has reached their daily limit!")
        else:
            print(f"  [OK] Candidate can still apply ({daily_limit - applications_today} remaining)")
    except Exception as e:
        print(f"[ERROR] Failed to check daily limit: {e}")
        return
    
    print(f"\n[Test 4: Check Existing Application]")
    try:
        existing = await check_existing_application(test_cand_id, test_requirement_id)
        if existing:
            print(f"[SUCCESS] Existing application found:")
            print(f"  Application ID: {existing.get('application_id')}")
            print(f"  Status: {existing.get('application_status')}")
            print(f"  Created: {existing.get('created_at')}")
        else:
            print(f"[SUCCESS] No existing application found for requirement_id={test_requirement_id}")
    except Exception as e:
        print(f"[ERROR] Failed to check existing application: {e}")
        return
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_preferences_service())
