"""
Chunk 6: FastAPI Application Entrypoint & SSE Streaming
-------------------------------------------------------
Educational Note for Students:
FastAPI is ideal for AI applications:
1. Native asynchronous request handling (async / await)
2. Streaming Server-Sent Events (SSE) using Starlette's StreamingResponse
3. Automatic OpenAPI documentation at /docs
4. Pydantic request & response validation
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import HOST, PORT, HAS_KEY
from models.spec import AppSpec
from pipeline import forge, modify, solo_benchmark

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("appforge.api")

app = FastAPI(
    title="AppForge Swarm API",
    description="One sentence → Multi-Agent Swarm → Deterministic Verifier → Safe Mini-App",
    version="2.0.0",
)

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ForgeRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500, description="User description of the desired mini-app")

class ModifyRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500, description="Change request")
    spec: Dict[str, Any] = Field(description="Current app specification to modify")

class SoloRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)

async def event_stream_generator(worker_coro) -> AsyncGenerator[str, None]:
    """Asynchronous generator yielding Server-Sent Events formatted as 'data: {...}\\n\\n'."""
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: Dict[str, Any]):
        queue.put_nowait(event)

    async def run_worker():
        try:
            await worker_coro(emit)
        except Exception as e:
            logger.exception("Pipeline execution failed")
            queue.put_nowait({"type": "error", "message": str(e)})
        finally:
            queue.put_nowait(None)  # Sentinel to end stream

    task = asyncio.create_task(run_worker())

    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event)}\n\n"

    await task

@app.get("/api/health")
async def health_check():
    """Health status and LLM key check."""
    return {"ok": True, "hasKey": HAS_KEY}

@app.post("/api/forge")
async def forge_app(req: ForgeRequest):
    """SSE endpoint: Forge a new application from a one-sentence prompt."""
    logger.info(f"Forge requested: '{req.prompt}'")
    return StreamingResponse(
        event_stream_generator(lambda emit: forge(req.prompt, emit)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/api/modify")
async def modify_app(req: ModifyRequest):
    """SSE endpoint: Modify an existing app via Orchestrator routing."""
    logger.info(f"Modify requested: '{req.prompt}'")
    try:
        current_spec = AppSpec.model_validate(req.spec)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid current spec: {e}")

    return StreamingResponse(
        event_stream_generator(lambda emit: modify(req.prompt, current_spec, emit)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/api/solo")
async def solo_comparison(req: SoloRequest):
    """Execute monolithic 1-shot baseline for educational comparison."""
    logger.info(f"Solo baseline requested: '{req.prompt}'")
    return await solo_benchmark(req.prompt)

if __name__ == "__main__":
    logger.info(f"Starting AppForge FastAPI server on http://{HOST}:{PORT} (Groq: {'Enabled' if HAS_KEY else 'Demo Mode'})")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
