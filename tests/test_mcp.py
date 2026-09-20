import asyncio
import sys
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from sinchai import db
from sinchai.farm import _seed_data
import tomllib, importlib.resources


@pytest.fixture
def seeded_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    con = db.open_db(db_path)
    cfg = tomllib.loads(importlib.resources.files("sinchai").joinpath("defaults.toml").read_bytes().decode())
    _seed_data(con, cfg)
    con.close()
    return db_path


@pytest.mark.asyncio
async def test_mcp_list_zones(seeded_db):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sinchai.mcp_server"],
        env={"SINCHAI_DB": seeded_db},
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            assert "list_zones" in names
            assert "get_zone_status" in names
            assert "request_valve" in names


@pytest.mark.asyncio
async def test_mcp_bad_zone_id(seeded_db):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sinchai.mcp_server"],
        env={"SINCHAI_DB": seeded_db},
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("get_zone_status", {"zone_id": 999})
            text = result.content[0].text if result.content else ""
            assert "not found" in text or "error" in text.lower()


@pytest.mark.asyncio
async def test_mcp_valve_gate_off(seeded_db):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sinchai.mcp_server"],
        env={"SINCHAI_DB": seeded_db},
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("request_valve", {"zone_id": 1, "action": "open", "minutes": 30})
            text = result.content[0].text if result.content else ""
            assert "disabled" in text or "false" in text.lower()
