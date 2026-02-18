"""
FastAPI Routes for Job Scraper API
Handles all scraping-related endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional
import asyncio
from datetime import datetime



from core.config import settings
from utils.logging import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/scrape", tags=["Scraper"])


@router.post("/batch")
async def start_batch_scrape(
   
):
    pass
