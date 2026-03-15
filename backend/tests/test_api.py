import pytest
import uuid
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from supabase import Client

from main import app
from app.database.database import get_db

@pytest.fixture
def anyio_backend():
    return 'asyncio'

# --- Mock Database ---
async def override_get_db():
    try:
        Client = AsyncMock(spec=Client)  
        # Implement minimal async methods if needed, mostly AsyncMock does magic
        Client.commit = AsyncMock()
        Client.rollback = AsyncMock()
        yield Client
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_trigger_scan():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # We need to mock background task to avoid actual execution or verify it was called
        # But FastAPI BackgroundTasks are hard to intercept without running them.
        # Since we use dependency injection for db in the background task, the real one runs.
        # It's better to mock the background task function `scan_aws_resources`
        
        with patch("app.api.resources_router.scan_aws_resources", new_callable=AsyncMock) as mock_scan:
            response = await ac.post("/api/v1/scan")
        
        assert response.status_code == 202
        data = response.json()
        assert "scan_job_id" in data
        assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_get_forecast():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/cost/forecast")
        assert response.status_code == 200
        data = response.json()
        assert "predicted_cost" in data
        assert data["forecast_period"] == "30 days"

@pytest.mark.asyncio
async def test_get_ec2_resources():
    # Mock database Client execute result
    mock_result = AsyncMock()
    mock_result.scalars().all.return_value = [
        {"id": "i-123", "region": "us-east-1", "state": "running"}
    ]
    
    # We need a more complex override if we want query results from DB mock
    # For now, just checking the endpoint is reachable and handles responses
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Patch the Client.execute within the dependency override if possible or mock the whole dependency
        # For this example, we accept empty list or whatever default behavior of AsyncMock
        response = await ac.get("/api/v1/resources/ec2")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

