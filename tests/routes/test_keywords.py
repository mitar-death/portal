"""
Tests for keywords routes.
"""
import pytest
from fastapi import status


class TestKeywordsRoutes:
    """Test keywords route endpoints."""

    @pytest.mark.asyncio
    async def test_get_keywords_success(self, client, auth_headers, test_keyword):
        """Test successful keywords retrieval."""
        response = client.get("/api/keywords", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["keyword"] == test_keyword.keyword

    @pytest.mark.asyncio
    async def test_get_keywords_unauthenticated(self, client):
        """Test keywords retrieval without authentication."""
        response = client.get("/api/keywords")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_create_keyword_success(self, client, auth_headers):
        """Test successful keyword creation."""
        response = client.post("/api/keywords", 
                             headers=auth_headers,
                             json={"keyword": "new_keyword"})
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        assert data["data"]["keyword"] == "new_keyword"

    @pytest.mark.asyncio
    async def test_create_keyword_duplicate(self, client, auth_headers, test_keyword):
        """Test keyword creation with duplicate keyword."""
        response = client.post("/api/keywords", 
                             headers=auth_headers,
                             json={"keyword": test_keyword.keyword})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_update_keyword_success(self, client, auth_headers, test_keyword):
        """Test successful keyword update."""
        response = client.put(f"/api/keywords/{test_keyword.id}", 
                            headers=auth_headers,
                            json={
                                "keyword": "updated_keyword",
                                "is_active": False
                            })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["keyword"] == "updated_keyword"
        assert data["data"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_keyword_not_found(self, client, auth_headers):
        """Test keyword update for non-existent keyword."""
        response = client.put("/api/keywords/999999", 
                            headers=auth_headers,
                            json={"keyword": "updated"})
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_keyword_success(self, client, auth_headers, test_keyword):
        """Test successful keyword deletion."""
        response = client.delete(f"/api/keywords/{test_keyword.id}", 
                               headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_keyword_not_found(self, client, auth_headers):
        """Test keyword deletion for non-existent keyword."""
        response = client.delete("/api/keywords/999999", 
                               headers=auth_headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bulk_update_keywords_success(self, client, auth_headers):
        """Test successful bulk keyword update."""
        keywords_data = [
            {"keywords": ["keyword1"]},
            {"keywords": ["keyword2"]}
        ]
        
        response = client.post("/api/keywords/bulk", 
                             headers=auth_headers,
                             json={"keywords": keywords_data})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True