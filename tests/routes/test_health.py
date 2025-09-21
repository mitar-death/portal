"""
Tests for health check routes.
"""
import pytest
from fastapi import status


class TestHealthRoutes:
    """Test health check route endpoints."""

    def test_health_check_success(self, client):
        """Test successful health check."""
        response = client.get("/api/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_ready_check_success(self, client):
        """Test successful readiness check."""
        response = client.get("/api/health/ready")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"

    def test_live_check_success(self, client):
        """Test successful liveness check."""
        response = client.get("/api/health/live")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"