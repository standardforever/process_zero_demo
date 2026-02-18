
"""
Job Scraper API - Main Application
FastAPI application for managing job scraping operations
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio

from api.v1.routes import browser

from core.config import settings
from utils.logging import setup_logger

from middlewares.trace_id_middleware import TraceIDMiddleware
from middlewares.logger_middleware import LoggingMiddleware



logger = setup_logger(__name__)

# Application version
VERSION = "1.0.0"



# Create FastAPI application
app = FastAPI(
    title="Job Scraper API",
    description="""
    API for managing browser automation
    """,
    version=VERSION,

)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Added logging middleware
app.add_middleware(LoggingMiddleware)

#Trace ID middleware
app.add_middleware(TraceIDMiddleware)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error": str(exc)
        }
    )


# Include routers
app.include_router(browser.router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Job Scraper API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/health",
        "scraper": "/scrape"
    }


@app.get("/ping", tags=["Health"])
async def ping():
    """Simple ping endpoint for load balancers"""
    return {"status": "ok"}


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

