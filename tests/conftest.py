"""
Pytest configuration and fixtures for TGPortal backend tests.
"""
import asyncio
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from server.app.main import app
from server.app.core.databases import Base, get_async_session
from server.app.models.models import User, Group, Keyword, AIAccount
from server.app.core.config import settings


# Test database URL - using in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=pool.StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    """Create async test database session."""
    async_session_maker = sessionmaker(
        async_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def client(async_session):
    """Create test client with database override."""
    def override_get_async_session():
        return async_session
    
    app.dependency_overrides[get_async_session] = override_get_async_session
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(async_session):
    """Create a test user."""
    user = User(
        phone_number="+1234567890",
        is_active=True,
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def test_group(async_session):
    """Create a test group."""
    group = Group(
        group_id=-1001234567890,
        title="Test Group",
        username="testgroup",
        is_monitored=True,
        member_count=100
    )
    async_session.add(group)
    await async_session.commit()
    await async_session.refresh(group)
    return group


@pytest.fixture
async def test_keyword(async_session, test_user):
    """Create a test keyword."""
    keyword = Keyword(
        user_id=test_user.id,
        keyword="test",
        is_active=True
    )
    async_session.add(keyword)
    await async_session.commit()
    await async_session.refresh(keyword)
    return keyword


@pytest.fixture
async def test_ai_account(async_session, test_user):
    """Create a test AI account."""
    ai_account = AIAccount(
        user_id=test_user.id,
        phone_number="+9876543210",
        first_name="AI",
        last_name="Assistant",
        is_active=True,
        session_string="test_session_string"
    )
    async_session.add(ai_account)
    await async_session.commit()
    await async_session.refresh(ai_account)
    return ai_account


@pytest.fixture
def mock_telegram_client():
    """Mock Telegram client."""
    client = AsyncMock()
    client.is_connected.return_value = True
    client.is_user_authorized.return_value = True
    client.get_me.return_value = MagicMock(
        id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User",
        phone="+1234567890"
    )
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    client = AsyncMock()
    client.ping.return_value = True
    client.get.return_value = None
    client.set.return_value = True
    client.delete.return_value = 1
    client.exists.return_value = False
    return client


@pytest.fixture
def mock_ai_engine():
    """Mock AI engine for testing."""
    with patch('server.app.services.ai_engine.generate_response') as mock:
        mock.return_value = "Test AI response"
        yield mock


@pytest.fixture
def temp_session_dir():
    """Create temporary directory for session files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_base_dir = getattr(settings, 'BASE_SESSION_DIR', None)
        settings.BASE_SESSION_DIR = temp_dir
        yield temp_dir
        if original_base_dir:
            settings.BASE_SESSION_DIR = original_base_dir


@pytest.fixture
def jwt_token(test_user):
    """Create a valid JWT token for testing."""
    from server.app.core.jwt_utils import create_token_pair
    
    tokens = create_token_pair(test_user.id)
    return tokens["access_token"]


@pytest.fixture
def auth_headers(jwt_token):
    """Create authorization headers with JWT token."""
    return {"Authorization": f"Bearer {jwt_token}"}


# Environment patches for testing
@pytest.fixture(autouse=True)
def mock_environment():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        'TELEGRAM_API_ID': '123456',
        'TELEGRAM_API_HASH': 'test_hash',
        'GOOGLE_STUDIO_API_KEY': 'test_api_key',
        'DATABASE_URL': TEST_DATABASE_URL,
        'SECRET_KEY': 'test_secret_key',
        'ENVIRONMENT': 'test'
    }):
        yield


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager."""
    manager = AsyncMock()
    manager.broadcast_message = AsyncMock()
    manager.send_personal_message = AsyncMock()
    return manager


@pytest.fixture
def mock_pusher_client():
    """Mock Pusher client."""
    client = MagicMock()
    client.trigger.return_value = True
    return client