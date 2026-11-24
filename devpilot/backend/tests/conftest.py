import os
import shutil
from typing import AsyncGenerator
import pytest_asyncio
from app.core.config import get_settings
from app.database.session import Base, engine, initialize_database
from app.services.llm_provider import LLMProviderFactory, MockLLMProvider


@pytest_asyncio.fixture(autouse=True)
async def setup_test_environment() -> AsyncGenerator[None, None]:
    mock_provider = MockLLMProvider()
    LLMProviderFactory.set_provider(mock_provider)

    await initialize_database()
    yield

    LLMProviderFactory.reset()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    settings = get_settings()
    if os.path.exists(settings.checkpoint_db_path):
        try:
            os.remove(settings.checkpoint_db_path)
        except OSError:
            pass

    if os.path.exists(settings.workspace_base_path):
        try:
            shutil.rmtree(settings.workspace_base_path)
        except OSError:
            pass
