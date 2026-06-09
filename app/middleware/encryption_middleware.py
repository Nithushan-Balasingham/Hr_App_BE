import json
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.deps import request_ip_ctx, request_user_agent_ctx
from app.core.encryption import EncryptionError, decrypt_payload, encrypt_payload


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
        token_ip = request_ip_ctx.set(ip)
        token_ua = request_user_agent_ctx.set(request.headers.get("user-agent"))
        try:
            return await call_next(request)
        finally:
            request_ip_ctx.reset(token_ip)
            request_user_agent_ctx.reset(token_ua)


class EncryptionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, api_prefix: str = "/api"):
        super().__init__(app)
        self.api_prefix = api_prefix

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        if not request.url.path.startswith(self.api_prefix):
            return await call_next(request)

        body = await request.body()
        if body:
            try:
                envelope = json.loads(body)
                decrypted = decrypt_payload(envelope)
                request._body = json.dumps(decrypted).encode("utf-8")
            except (json.JSONDecodeError, EncryptionError, KeyError):
                encrypted_error = encrypt_payload({"detail": "Invalid encrypted payload"})
                return JSONResponse(status_code=400, content=encrypted_error)

        response = await call_next(request)

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        if not response_body:
            encrypted_empty = encrypt_payload({})
            return JSONResponse(
                status_code=response.status_code,
                content=encrypted_empty,
                headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            )

        try:
            plaintext = json.loads(response_body)
        except json.JSONDecodeError:
            plaintext = {"detail": response_body.decode("utf-8", errors="replace")}

        encrypted = encrypt_payload(plaintext)
        return JSONResponse(
            status_code=response.status_code,
            content=encrypted,
            headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
        )
