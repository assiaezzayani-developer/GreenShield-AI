from fastapi.testclient import TestClient
from backend.main import app

def test_health():
 r=TestClient(app).get('/api/health')
 assert r.status_code==200 and r.json()['status']=='ok'

def test_auth_required():
 assert TestClient(app).get('/api/plants').status_code==401

def test_invalid_login():
 assert TestClient(app).post('/api/auth/login',json={'email':'invalid@example.com','password':'bad'}).status_code==401
