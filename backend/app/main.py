"""FastAPI application entry point for the SaaS backend layer."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.activity import router as activity_router
from backend.app.api.v1.approval import router as approval_router
from backend.app.api.v1.content import router as content_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.scheduler import router as scheduler_router

app = FastAPI(
    title="LinkedIn Content SaaS API",
    version="0.1.0",
    description=(
        "REST API surface for the existing LinkedIn content orchestration "
        "engine."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(content_router)
app.include_router(dashboard_router)
app.include_router(activity_router)
app.include_router(approval_router)
app.include_router(scheduler_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
