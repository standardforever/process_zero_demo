from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat, data, rules, rules_ai, schema_store, transform

app = FastAPI(
    title="CRM-to-ERP Transformer API",
    version="1.0.0",
    root_path="/transformer",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(rules_ai.router, prefix="/api")
app.include_router(schema_store.router, prefix="/api")
app.include_router(transform.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "crm-to-erp-transformer"}


@app.get("/api")
@app.get("/api/")
def api_root() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "crm-to-erp-transformer",
        "docs": "./docs",
        "openapi": "./openapi.json",
    }
