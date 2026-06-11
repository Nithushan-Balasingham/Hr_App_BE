print("FASTAPI APP LOADED")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.middleware.encryption_middleware import AuditContextMiddleware, EncryptionMiddleware
from app.routers import audit_logs, auth, departments, employees, leave, modules, roles

settings = get_settings()

app = FastAPI(title="HR Portal API", version="1.0.0")
try:
    from sqlalchemy.dialects.mysql.aiomysql import (
        AsyncAdapt_aiomysql_connection,
    )

    _orig_ping = AsyncAdapt_aiomysql_connection.ping

    def _patched_ping(self, reconnect=False):
        return _orig_ping(self, reconnect)

    AsyncAdapt_aiomysql_connection.ping = _patched_ping
except ImportError:
    pass


app.add_middleware(AuditContextMiddleware)
app.add_middleware(EncryptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(modules.router)
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(leave.router)
app.include_router(roles.router)
app.include_router(audit_logs.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
