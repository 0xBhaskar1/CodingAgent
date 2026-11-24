import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_projects_crud_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_res = await client.post(
            "/api/projects",
            json={"name": "DevPilot Core", "description": "Core engine"},
        )
        assert create_res.status_code == 201
        project_data = create_res.json()
        project_id = project_data["id"]
        assert project_data["name"] == "DevPilot Core"

        get_res = await client.get(f"/api/projects/{project_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == project_id

        list_res = await client.get("/api/projects")
        assert list_res.status_code == 200
        projects = list_res.json()
        assert any(p["id"] == project_id for p in projects)


@pytest.mark.asyncio
async def test_sessions_crud_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post(
            "/api/projects",
            json={"name": "Auth Service"},
        )
        project_id = proj_res.json()["id"]

        session_res = await client.post(
            "/api/sessions",
            json={
                "project_id": project_id,
                "task_description": "Implement OAuth2 flow",
            },
        )
        assert session_res.status_code == 201
        session_data = session_res.json()
        session_id = session_data["id"]
        assert session_data["status"] == "created"

        get_session_res = await client.get(f"/api/sessions/{session_id}")
        assert get_session_res.status_code == 200
        assert get_session_res.json()["id"] == session_id


@pytest.mark.asyncio
async def test_agent_run_approval_lifecycle_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post("/api/projects", json={"name": "Worker"})
        project_id = proj_res.json()["id"]

        session_res = await client.post(
            "/api/sessions",
            json={
                "project_id": project_id,
                "task_description": "Create background worker",
            },
        )
        session_id = session_res.json()["id"]

        run_res = await client.post(f"/api/agent/{session_id}/run")
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["current_step"] == "awaiting_approval"

        status_res = await client.get(f"/api/agent/{session_id}/status")
        assert status_res.status_code == 200
        assert status_res.json()["current_step"] == "awaiting_approval"

        approve_res = await client.post(
            f"/api/agent/{session_id}/approve",
            json={"feedback": "Looks great, proceed"},
        )
        assert approve_res.status_code == 200
        approve_data = approve_res.json()
        assert approve_data["final_status"] == "completed"

        after_status_res = await client.get(f"/api/agent/{session_id}/status")
        assert after_status_res.status_code == 200
        assert after_status_res.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_agent_run_reject_lifecycle_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post("/api/projects", json={"name": "Worker Reject"})
        project_id = proj_res.json()["id"]

        session_res = await client.post(
            "/api/sessions",
            json={
                "project_id": project_id,
                "task_description": "Build questionable script",
            },
        )
        session_id = session_res.json()["id"]

        await client.post(f"/api/agent/{session_id}/run")
        reject_res = await client.post(
            f"/api/agent/{session_id}/reject",
            json={"feedback": "Rejected: bad plan"},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["final_status"] == "rejected"

        status_res = await client.get(f"/api/agent/{session_id}/status")
        assert status_res.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_system_config_and_session_files_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        config_res = await client.get("/api/system/config")
        assert config_res.status_code == 200
        config_data = config_res.json()
        assert "provider" in config_data
        assert "gemini_configured" in config_data
        assert "api_key" not in config_data

        proj_res = await client.post("/api/projects", json={"name": "File Project"})
        project_id = proj_res.json()["id"]

        sess_res = await client.post(
            "/api/sessions",
            json={"project_id": project_id, "task_description": "File task"},
        )
        session_id = sess_res.json()["id"]

        list_sess_res = await client.get(f"/api/sessions?project_id={project_id}")
        assert list_sess_res.status_code == 200
        assert len(list_sess_res.json()) >= 1

        files_res = await client.get(f"/api/sessions/{session_id}/files")
        assert files_res.status_code == 200
        assert isinstance(files_res.json(), list)

        put_file_res = await client.put(
            f"/api/sessions/{session_id}/files/example.py",
            json={"content": "print('hello')\n"},
        )
        assert put_file_res.status_code == 200

        files_after_res = await client.get(f"/api/sessions/{session_id}/files")
        assert files_after_res.status_code == 200
        files = files_after_res.json()
        assert any(f["path"] == "example.py" for f in files)

