# SPDX-FileCopyrightText: 2026 AOT Technologies
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from m8flow_node_wire_proxy.adapter import execute_http_v2
from m8flow_node_wire_proxy.catalog import HTTP_V2_COMMANDS
from m8flow_node_wire_proxy.node_wire_gateway import ensure_allowed_connectors


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    ensure_allowed_connectors()
    # Import after allowlist is set so entry-point discovery stays fail-closed.
    import node_wire_http_generic  # noqa: F401
    import node_wire_runtime  # noqa: F401

    yield


app = FastAPI(
    title="m8flow-node-wire-proxy",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/liveness")
def liveness() -> dict[str, Any]:
    """Compose healthcheck target — same shape as m8flow-connector-proxy."""
    return {"ok": True}


@app.get("/v1/commands")
def list_commands() -> list[dict[str, Any]]:
    """Spiff-compatible operator catalog (HTTP V2 only for this POC)."""
    return HTTP_V2_COMMANDS


@app.post("/v1/do/{connector}/{command}")
async def do_command(connector: str, command: str, request: Request) -> dict[str, Any]:
    """Execute a catalogued operator; always HTTP 200 with V2 envelope."""
    raw = await request.json()
    if not isinstance(raw, dict):
        raw = {}
    return await execute_http_v2(connector, command, raw)
