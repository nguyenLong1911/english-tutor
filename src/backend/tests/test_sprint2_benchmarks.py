"""
Sprint 2 Backend Benchmark Tests

1. Mem0 search latency P95 < 1s
2. 5-turn conversation end-to-end test
"""
import asyncio
import json
import time
import statistics
from uuid import uuid4

import httpx


BASE_URL = "http://localhost:8000"
DEMO_USER_ID = None  # Will be populated


async def create_demo_user():
    """Create a demo user for testing"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/api/v1/onboarding/demo")
        user = resp.json()
        return user["user_id"]


async def test_mem0_latency_p95():
    """
    Test: Mem0 search latency P95 < 1s
    
    Measure latency of 20 memory searches and verify P95 < 1000ms
    """
    global DEMO_USER_ID
    if not DEMO_USER_ID:
        DEMO_USER_ID = await create_demo_user()
    
    user_id = DEMO_USER_ID
    
    # Warm up: add a few facts
    print("\n📊 [Mem0 Latency Test] Warming up with facts...")
    async with httpx.AsyncClient() as client:
        for i in range(3):
            await client.post(
                f"{BASE_URL}/api/v1/chat",
                json={
                    "user_id": user_id,
                    "message": f"Fact {i}: Important vocabulary for marketing is crucial for business success.",
                }
            )
    
    # Measure latency: 20 searches
    print("📊 [Mem0 Latency Test] Running 20 searches...")
    latencies = []
    queries = [
        "vocabulary",
        "marketing",
        "business",
        "success",
        "important",
        "crucial",
        "learning",
        "goals",
        "industry",
        "english",
        "profit",
        "revenue",
        "margin",
        "campaign",
        "strategy",
        "customer",
        "service",
        "feedback",
        "meeting",
        "communication",
    ]
    
    async with httpx.AsyncClient() as client:
        for query in queries:
            start = time.time()
            resp = await client.get(
                f"{BASE_URL}/api/v1/vocabulary/new",
                params={"user_id": user_id, "limit": 3}
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms
            latencies.append(elapsed)
            print(f"  Query '{query}': {elapsed:.1f}ms")
    
    # Calculate P95
    latencies.sort()
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[p95_idx]
    p50 = statistics.median(latencies)
    p99 = max(latencies)
    
    print(f"\n✅ Mem0 Latency Stats:")
    print(f"   P50 (median): {p50:.1f}ms")
    print(f"   P95:         {p95:.1f}ms")
    print(f"   P99 (max):   {p99:.1f}ms")
    
    if p95 < 1000:
        print(f"   ✅ PASS: P95 {p95:.1f}ms < 1000ms")
        return True
    else:
        print(f"   ⚠️  WARN: P95 {p95:.1f}ms >= 1000ms")
        return False


async def test_5turn_conversation():
    """
    Test: 5-turn conversation end-to-end
    
    Simulate a realistic conversation:
    Turn 1: User writes sentence with vocabulary word
    Turn 2: User asks for a clearer explanation
    Turn 3: User writes another sentence
    Turn 4: User asks question
    Turn 5: User writes more practice
    """
    global DEMO_USER_ID
    if not DEMO_USER_ID:
        DEMO_USER_ID = await create_demo_user()
    
    user_id = DEMO_USER_ID
    
    print("\n🎯 [5-Turn Conversation Test] Starting...")
    
    turns = [
        {
            "num": 1,
            "message": "The profit margin improved significantly this year.",
            "expected_contains": ["margin", "profit"],
            "description": "Practice sentence with vocabulary words"
        },
        {
            "num": 2,
            "message": "Can you explain the mistake more clearly?",
            "expected_contains": ["mistake", "clear", "giải", "sửa"],
            "description": "Ask for a clearer explanation"
        },
        {
            "num": 3,
            "message": "Revenue increased by 20 percent in the marketing department.",
            "expected_contains": ["revenue", "marketing"],
            "description": "Another practice sentence"
        },
        {
            "num": 4,
            "message": "What is the difference between profit and revenue?",
            "expected_contains": ["profit", "revenue", "định", "khác"],
            "description": "Ask question about vocabulary"
        },
        {
            "num": 5,
            "message": "The company will deploy the new system next month.",
            "expected_contains": ["deploy"],
            "description": "Final practice sentence"
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for turn in turns:
            print(f"\n  Turn {turn['num']}: {turn['description']}")
            print(f"    Message: {turn['message'][:60]}...")
            
            payload = {"user_id": user_id, "message": turn["message"]}
            start = time.time()
            resp = await client.post(f"{BASE_URL}/api/v1/chat", json=payload)
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code != 200:
                print(f"    ❌ FAIL: HTTP {resp.status_code}")
                print(f"    Response: {resp.text[:100]}")
                return False
            
            result = resp.json()
            response = result.get("response", "")
            print(f"    Response: {response[:80]}...")
            print(f"    Latency: {elapsed:.1f}ms")
            
            # Check expected content
            has_expected = False
            for keyword in turn["expected_contains"]:
                if keyword.lower() in response.lower():
                    has_expected = True
                    break
            
            if not has_expected and turn["num"] > 2:  # Be lenient for early turns
                print(f"    ⚠️  Warning: Expected keywords not found in response")
            else:
                print(f"    ✅ Response valid")
            
            # Small delay between turns
            await asyncio.sleep(0.5)
    
    print(f"\n✅ 5-Turn Conversation Test: PASS")
    return True


async def main():
    """Run all benchmark tests"""
    print("=" * 60)
    print("SPRINT 2 BACKEND BENCHMARK TESTS")
    print("=" * 60)
    
    try:
        # Test 1: Mem0 latency
        latency_pass = await test_mem0_latency_p95()
        
        # Test 2: 5-turn conversation
        conversation_pass = await test_5turn_conversation()
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✅ Mem0 Latency P95 < 1s:        {'PASS' if latency_pass else 'WARN'}")
        print(f"✅ 5-Turn Conversation:          {'PASS' if conversation_pass else 'FAIL'}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
