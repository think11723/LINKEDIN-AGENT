"""FastAPI application for LinkedIn Content Agent.

This is the main entry point for the web API.
"""

from fastapi import FastAPI

app = FastAPI(
    title="LinkedIn Agent",
    description="AI-powered LinkedIn Content Assistant",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "linkedin-agent"
    }
