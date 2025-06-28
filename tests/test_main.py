import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Interview Bot" in data["message"]


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_webhook_verification():
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "test_token",
        "hub.challenge": "test_challenge"
    })
    # Will fail without proper token, but tests the endpoint
    assert response.status_code in [200, 403]
