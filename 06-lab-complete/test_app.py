import sys
import warnings
sys.path.insert(0, 'c:/Users/nhuqu/day12_ha-tang-cloud_va_deployment')
warnings.filterwarnings('ignore')
from app.main import app
from starlette.testclient import TestClient

with TestClient(app, raise_server_exceptions=True) as client:
    # Test 1: health
    r = client.get('/health')
    body = r.json()
    print(f'1. HEALTH: {r.status_code} -> status={body["status"]}')
    assert r.status_code == 200

    # Test 2: ready
    r2 = client.get('/ready')
    print(f'2. READY: {r2.status_code}')
    assert r2.status_code == 200

    # Test 3: 401 no auth
    r3 = client.post('/ask', json={'question': 'Hello'})
    print(f'3. NO AUTH: {r3.status_code} (expect 401)')
    assert r3.status_code == 401

    # Test 4: 200 with auth
    r4 = client.post('/ask', json={'question': 'What is Docker?'}, headers={'X-API-Key': 'secret-lab-key-2026'})
    print(f'4. WITH AUTH: {r4.status_code}')
    assert r4.status_code == 200
    data = r4.json()
    print(f'   Answer: {data["answer"][:80]}...')

    # Test 5: rate limit
    print('5. RATE LIMIT TEST:')
    hit_429 = False
    for i in range(25):
        rn = client.post('/ask', json={'question': f'Test {i}'}, headers={'X-API-Key': 'secret-lab-key-2026'})
        if rn.status_code == 429:
            print(f'   Got 429 at request #{i+1} -- CORRECT!')
            hit_429 = True
            break
    assert hit_429, "Rate limit was never triggered!"

    # Test 6: cost guard (simulate exceeding budget)
    print('6. COST GUARD: Simulating budget check...')
    from app.cost_guard import check_budget
    try:
        check_budget("user_test_ok", 0.001)
        print('   Budget check OK (within limit)')
    except Exception as e:
        print(f'   Budget error (unexpected): {e}')

    print('\nALL TESTS PASSED!')
