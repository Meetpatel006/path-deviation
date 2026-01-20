"""
Basic API endpoint tests for Phase 1
"""
import pytest
from fastapi import status


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_start_journey_validation(client, sample_journey_request):
    """Test journey start validation"""
    # Test with invalid latitude
    invalid_request = sample_journey_request.copy()
    invalid_request["origin"]["lat"] = 100  # Invalid latitude
    response = client.post("/api/journey/start", json=invalid_request)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_gps_to_nonexistent_journey(client, sample_gps_point):
    """Test submitting GPS point to non-existent journey"""
    response = client.post(
        "/api/journey/fake-journey-id/gps",
        json=sample_gps_point
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_nonexistent_journey(client):
    """Test getting non-existent journey"""
    response = client.get("/api/journey/fake-journey-id")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Note: We can't test actual Mapbox integration without API key
# These tests will be expanded once we have proper test data
