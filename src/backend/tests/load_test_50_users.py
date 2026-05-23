"""Load test: 50 concurrent users hitting the backend API.

Verifies SPRINT 3 backend checkpoint:
    [ ] Load test: 50 concurrent users, 0% error rate

Run from host:
    python -m src.backend.tests.load_test_50_users
or in container:
    docker compose exec backend python tests/load_test_50_users.py
"""

import asyncio
import time
import uuid
from statistics import median

import httpx

BASE_URL = "http://localhost:8000"
N_USERS = 50
REQUESTS_PER_USER = 5  # 50 * 5 = 250 total; well under per-user 50 limit


async def user_session(client: httpx.AsyncClient, idx: int) -> dict:
    """Simulate one user: onboard, fetch profile, fetch vocab, fetch review."""
    errors = []
    latencies = []

    industry = ["technology", "finance", "healthcare", "education", "general"][idx % 5]
    payload = {
        "cefr_level": "A2",
        "industry": industry,
        "learning_goals": ["speaking", "writing"],
    }

    # 1) onboarding
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{BASE_URL}/api/v1/onboarding", json=payload, timeout=15)
        latencies.append(time.perf_counter() - t0)
        if r.status_code not in (200, 201):
            errors.append(f"onboarding_{r.status_code}")
            return {"errors": errors, "latencies": latencies}
        user_id = r.json()["user_id"]
    except Exception as exc:
        errors.append(f"onboarding_exc:{exc.__class__.__name__}")
        return {"errors": errors, "latencies": latencies}

    headers = {"X-User-ID": user_id}

    # 2) fetch profile, vocab, review (3 reads = 4 total per user incl. onboarding)
    endpoints = [
        f"/api/v1/user/{user_id}",
        f"/api/v1/vocabulary/new?user_id={user_id}&limit=3",
        f"/api/v1/review/due?user_id={user_id}",
        f"/api/v1/analytics/{user_id}/summary",
    ]
    for ep in endpoints[: REQUESTS_PER_USER - 1]:
        t0 = time.perf_counter()
        try:
            r = await client.get(f"{BASE_URL}{ep}", headers=headers, timeout=15)
            latencies.append(time.perf_counter() - t0)
            if r.status_code >= 400:
                errors.append(f"{ep}_{r.status_code}")
        except Exception as exc:
            errors.append(f"{ep}_exc:{exc.__class__.__name__}")

    return {"errors": errors, "latencies": latencies}


async def main() -> None:
    print(f"Load test: {N_USERS} concurrent users, {REQUESTS_PER_USER} req/user")
    limits = httpx.Limits(max_keepalive_connections=N_USERS, max_connections=N_USERS * 2)
    start = time.perf_counter()
    async with httpx.AsyncClient(limits=limits) as client:
        results = await asyncio.gather(*[user_session(client, i) for i in range(N_USERS)])
    elapsed = time.perf_counter() - start

    all_errors = [e for r in results for e in r["errors"]]
    all_latencies = [l for r in results for l in r["latencies"]]
    total_requests = sum(len(r["latencies"]) + len(r["errors"]) for r in results)

    print(f"\nTotal requests   : {total_requests}")
    print(f"Successful       : {len(all_latencies)}")
    print(f"Errors           : {len(all_errors)}")
    error_rate = (len(all_errors) / total_requests * 100) if total_requests else 0.0
    print(f"Error rate       : {error_rate:.2f}%")
    print(f"Wall time        : {elapsed:.2f}s")
    if all_latencies:
        all_latencies.sort()
        p50 = median(all_latencies)
        p95 = all_latencies[int(len(all_latencies) * 0.95)] if len(all_latencies) > 1 else all_latencies[0]
        print(f"Latency p50      : {p50*1000:.0f}ms")
        print(f"Latency p95      : {p95*1000:.0f}ms")
    if all_errors:
        print("\nFirst 10 errors:")
        for e in all_errors[:10]:
            print(f"  {e}")

    assert error_rate == 0.0, f"Load test failed: {error_rate:.2f}% errors"
    print("\nPASS: 0% error rate with 50 concurrent users")


if __name__ == "__main__":
    asyncio.run(main())
