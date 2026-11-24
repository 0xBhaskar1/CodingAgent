from fastapi import APIRouter
from app.api.v1.endpoints import agent, health, projects, sessions, system, tasks

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
