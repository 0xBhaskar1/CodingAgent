import aiosqlite
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.agent.graph import create_compiled_graph
from app.agent.state import create_initial_agent_state


@pytest.mark.asyncio
async def test_workflow_reaches_approval_and_pauses() -> None:
    async with aiosqlite.connect(":memory:") as conn:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        graph = await create_compiled_graph(checkpointer=saver)

        session_id = "test-session-approval-pause"
        config = {"configurable": {"thread_id": session_id}}
        init_state = create_initial_agent_state(session_id, "Build REST API for notes")

        result = await graph.ainvoke(init_state, config=config)

        assert result["current_step"] == "awaiting_approval"
        assert len(result["requirements"]) > 0
        assert len(result["implementation_plan"]) > 0
        assert result["approval_status"] == "pending"


@pytest.mark.asyncio
async def test_workflow_approved_plan_execution() -> None:
    async with aiosqlite.connect(":memory:") as conn:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        graph = await create_compiled_graph(checkpointer=saver)

        session_id = "test-session-approve-flow"
        config = {"configurable": {"thread_id": session_id}}
        init_state = create_initial_agent_state(session_id, "Build user model")

        turn1 = await graph.ainvoke(init_state, config=config)
        assert turn1["current_step"] == "awaiting_approval"

        await graph.aupdate_state(config, {"approval_status": "approved"})
        turn2 = await graph.ainvoke(None, config=config)

        assert turn2["current_step"] == "completed"
        assert turn2["final_status"] == "completed"
        assert turn2["approval_status"] == "approved"
        assert len(turn2["generated_files"]) > 0


@pytest.mark.asyncio
async def test_workflow_rejected_plan_routing() -> None:
    async with aiosqlite.connect(":memory:") as conn:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        graph = await create_compiled_graph(checkpointer=saver)

        session_id = "test-session-reject-flow"
        config = {"configurable": {"thread_id": session_id}}
        init_state = create_initial_agent_state(session_id, "Build dangerous script")

        turn1 = await graph.ainvoke(init_state, config=config)
        assert turn1["current_step"] == "awaiting_approval"

        await graph.aupdate_state(config, {"approval_status": "rejected"})
        turn2 = await graph.ainvoke(None, config=config)

        assert turn2["current_step"] == "completed"
        assert turn2["final_status"] == "rejected"
        assert turn2["approval_status"] == "rejected"
        assert len(turn2["generated_files"]) == 0
