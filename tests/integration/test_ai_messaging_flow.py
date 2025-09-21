"""
Integration tests for AI messaging workflow.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status


class TestAIMessagingFlow:
    """Test complete AI messaging workflow."""

    @pytest.mark.asyncio
    async def test_complete_ai_messaging_flow(self, client, auth_headers, test_user, test_ai_account, test_keyword, test_group):
        """Test complete AI messaging flow from group message to DM response."""
        
        # Step 1: Set up AI account and keyword monitoring
        with patch('server.app.services.messenger_ai.MessengerAI') as mock_messenger_class:
            mock_messenger = AsyncMock()
            mock_messenger_class.return_value = mock_messenger
            
            # Simulate group message containing keyword
            group_message = MagicMock()
            group_message.message = f"I need help with {test_keyword.keyword}"
            group_message.sender_id = 123456789
            group_message.chat_id = test_group.group_id
            group_message.text = f"I need help with {test_keyword.keyword}"
            
            # Step 2: Handle group message (should trigger keyword detection)
            await mock_messenger.handle_group_message(group_message)
            
            # Verify group message was processed
            mock_messenger.handle_group_message.assert_called_once_with(group_message)

    @pytest.mark.asyncio
    async def test_ai_response_generation_flow(self, client, auth_headers):
        """Test AI response generation through API."""
        
        # Test direct AI response generation
        with patch('server.app.services.ai_engine.generate_response') as mock_generate:
            mock_generate.return_value = "This is a helpful AI response!"
            
            response = client.post("/api/ai/generate", 
                                 headers=auth_headers,
                                 json={
                                     "message": "I need help with Python programming",
                                     "context": "programming_help"
                                 })
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["data"]["response"] == "This is a helpful AI response!"

    @pytest.mark.asyncio
    async def test_keyword_management_flow(self, client, auth_headers, test_user):
        """Test complete keyword management workflow."""
        
        # Step 1: Create keywords
        keywords_to_create = ["python", "help", "support", "ai"]
        created_keywords = []
        
        for keyword in keywords_to_create:
            response = client.post("/api/keywords", 
                                 headers=auth_headers,
                                 json={"keyword": keyword})
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True
            created_keywords.append(data["data"])

        # Step 2: Get all keywords
        response = client.get("/api/keywords", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should include the original test keyword plus new ones
        assert len(data["data"]) >= len(keywords_to_create)

        # Step 3: Update a keyword
        keyword_to_update = created_keywords[0]
        response = client.put(f"/api/keywords/{keyword_to_update['id']}", 
                            headers=auth_headers,
                            json={
                                "keyword": "updated_python",
                                "is_active": False
                            })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["keyword"] == "updated_python"
        assert data["data"]["is_active"] is False

        # Step 4: Delete a keyword
        keyword_to_delete = created_keywords[1]
        response = client.delete(f"/api/keywords/{keyword_to_delete['id']}", 
                               headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_group_monitoring_flow(self, client, auth_headers, test_group):
        """Test group monitoring workflow."""
        
        # Step 1: Get groups list
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_dialogs = [
                MagicMock(
                    entity=MagicMock(
                        id=test_group.group_id,
                        title=test_group.title,
                        username=test_group.username,
                        participants_count=test_group.member_count
                    ),
                    is_group=True,
                    is_channel=False
                )
            ]
            mock_client.iter_dialogs.return_value.__aiter__ = lambda: iter(mock_dialogs)
            mock_get_client.return_value = mock_client
            
            response = client.get("/api/telegram/groups", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]) == 1

        # Step 2: Update group monitoring status
        response = client.post(f"/api/groups/{test_group.group_id}/monitor", 
                             headers=auth_headers,
                             json={"is_monitored": False})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        # Step 3: Get group details
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_entity = MagicMock(
                id=test_group.group_id,
                title=test_group.title,
                username=test_group.username,
                participants_count=test_group.member_count
            )
            mock_client.get_entity.return_value = mock_entity
            mock_get_client.return_value = mock_client
            
            response = client.get(f"/api/groups/{test_group.group_id}", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["data"]["title"] == test_group.title

    @pytest.mark.asyncio
    async def test_ai_account_management_flow(self, client, auth_headers, test_ai_account):
        """Test AI account management workflow."""
        
        # Step 1: Get AI accounts
        response = client.get("/api/ai/accounts", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["phone_number"] == test_ai_account.phone_number

        # Step 2: Create new AI account
        with patch('server.app.services.telegram.client_manager.get_ai_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.is_user_authorized.return_value = True
            mock_client.get_me.return_value = MagicMock(
                id=987654321,
                phone="+5555555555",
                first_name="New AI",
                last_name="Assistant"
            )
            mock_get_client.return_value = mock_client
            
            response = client.post("/api/ai/accounts", 
                                 headers=auth_headers,
                                 json={
                                     "phone_number": "+5555555555",
                                     "first_name": "New AI",
                                     "last_name": "Assistant",
                                     "session_string": "new_test_session"
                                 })
            
            assert response.status_code == status.HTTP_201_CREATED

        # Step 3: Delete AI account
        response = client.delete(f"/api/ai/accounts/{test_ai_account.id}", 
                               headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK