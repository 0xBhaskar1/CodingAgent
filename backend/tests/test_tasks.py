import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_create_and_read_task() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "title": "Initial Task",
            "description": "Test creating a task in DevPilot",
        }
        create_response = await client.post("/api/v1/tasks", json=payload)
        assert create_response.status_code == 201
        created_task = create_response.json()
        assert created_task["title"] == payload["title"]
        assert created_task["description"] == payload["description"]
        assert created_task["status"] == "pending"
        task_id = created_task["id"]

        get_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.status_code == 200
        fetched_task = get_response.json()
        assert fetched_task["id"] == task_id

        list_response = await client.get("/api/v1/tasks")
        assert list_response.status_code == 200
        tasks = list_response.json()
        assert any(item["id"] == task_id for item in tasks)
