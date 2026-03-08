import requests
import json

BASE_URL = "https://wallfruits-backend.onrender.com"

print("=" * 60)
print("TESTANDO API WALLFRUITS NO RENDER")
print("=" * 60)

# Test 1: Root
print("\n1. Testando rota raiz /")
try:
    r = requests.get(f"{BASE_URL}/")
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text[:100]}")
except Exception as e:
    print(f"   Erro: {e}")

# Test 2: Docs
print("\n2. Testando /docs")
try:
    r = requests.get(f"{BASE_URL}/docs")
    print(f"   Status: {r.status_code}")
except Exception as e:
    print(f"   Erro: {e}")

# Test 3: API Docs
print("\n3. Testando /api/docs")
try:
    r = requests.get(f"{BASE_URL}/api/docs")
    print(f"   Status: {r.status_code}")
except Exception as e:
    print(f"   Erro: {e}")

# Test 4: Health
print("\n4. Testando /health")
try:
    r = requests.get(f"{BASE_URL}/health")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {r.json()}")
except Exception as e:
    print(f"   Erro: {e}")

# Test 5: API Health
print("\n5. Testando /api/health")
try:
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {r.json()}")
except Exception as e:
    print(f"   Erro: {e}")

# Test 6: Register
print("\n6. Testando POST /api/auth/register")
try:
    data = {
        "name": "Teste Usuario",
        "email": "teste999@example.com",
        "password": "senha123456",
        "role": "buyer"
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=data)
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text}")
except Exception as e:
    print(f"   Erro: {e}")

# Test 7: OpenAPI JSON
print("\n7. Testando /api/openapi.json")
try:
    r = requests.get(f"{BASE_URL}/api/openapi.json")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        openapi = r.json()
        print(f"   Rotas disponíveis:")
        for path in list(openapi.get('paths', {}).keys())[:10]:
            print(f"      - {path}")
except Exception as e:
    print(f"   Erro: {e}")

print("\n" + "=" * 60)
