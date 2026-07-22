from __future__ import annotations

import pytest

from app.mcp.ml_technical_server import mcp


@pytest.mark.asyncio
async def test_career_ledger_mcp_tools_are_read_only():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert "get_career_pipeline_summary" in names
    assert "get_career_pipeline_review_context" in names

    # No write path for application status, applications, vacancies or
    # strategy is exposed over MCP: only Telegram can call the service's
    # write methods (record_manual_application / append_application_event).
    forbidden_prefixes = ("create_career", "append_career", "update_career", "set_career")
    assert not any(name.startswith(forbidden_prefixes) for name in names)
