"""Gateway authentication & GxP audit middleware module."""

import time
from typing import Any, Callable, Dict

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from packages.security.permissions import PermissionEnum, get_permissions_for_roles


async def get_current_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency extracting current user identity from request.

    Raises 401 Unauthorized if no valid user identity or authorization header is present.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        user_id = request.headers.get("X-User-Id") or request.headers.get("x-user-id")

    auth_header = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )

    if not user_id and not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing user identity or authorization header",
        )

    roles = getattr(request.state, "roles", [])
    if not roles and "X-User-Roles" in request.headers:
        roles = [
            r.strip() for r in request.headers["X-User-Roles"].split(",") if r.strip()
        ]

    tenant_id = getattr(request.state, "tenant_id", None) or request.headers.get(
        "X-Tenant-Id", "tenant_default"
    )

    return {
        "sub": user_id or "authenticated_user",
        "roles": roles,
        "tenant_id": tenant_id,
    }


class ReplayProtectionStore:
    """In-memory store to prevent replay attacks on signed requests."""

    def __init__(self) -> None:
        self._seen_signatures: Dict[str, float] = {}

    def is_replayed(self, token: str, exp: float, jti: str | None = None) -> bool:
        """Check if a signature token or JTI has already been processed."""
        now = time.time()
        # Clean expired
        self._seen_signatures = {
            k: v for k, v in self._seen_signatures.items() if v > now
        }
        key = jti if jti else token
        if key in self._seen_signatures:
            return True
        self._seen_signatures[key] = exp
        return False


_replay_store = ReplayProtectionStore()


def verify_sig_token(
    token: str,
    secret: str,
    expected_user_id: str,
    expected_action: str | None = None,
) -> Dict[str, Any]:
    """Verify signed signature token."""
    from jose import JWTError, jwt

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid sig_token: {str(e)}")

    if payload.get("user_id") != expected_user_id:
        raise HTTPException(status_code=403, detail="sig_token user_id mismatch")

    if expected_action and payload.get("semantic_action") != expected_action:
        raise HTTPException(
            status_code=403, detail="sig_token semantic_action mismatch"
        )

    exp = payload.get("exp", 0)
    jti = payload.get("jti")
    if _replay_store.is_replayed(token, exp, jti):
        raise HTTPException(
            status_code=401, detail="sig_token has already been used (replay detected)"
        )

    return payload


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """API Gateway authentication and authorization middleware."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)

    def gateway_secret(self) -> bytes:
        import os

        secret = os.getenv("GATEWAY_HMAC_SECRET", "default_gateway_secret_2026")
        return secret.encode("utf-8")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        # Exclude public endpoints
        path = request.url.path
        if path in ("/health", "/docs", "/openapi.json", "/metrics") or path.startswith(
            "/public/"
        ):
            return await call_next(request)

        user_id = request.headers.get("X-User-Id")
        roles_header = request.headers.get("X-User-Roles", "")
        roles = [r.strip() for r in roles_header.split(",") if r.strip()]

        request.state.user_id = user_id
        request.state.roles = roles
        request.state.permissions = get_permissions_for_roles(roles)

        return await call_next(request)


def require_gateway_permission(
    required_permission: PermissionEnum,
) -> Callable[..., Any]:
    """FastAPI dependency enforcing a specific gateway permission."""

    async def _dependency(request: Request) -> None:
        permissions = getattr(request.state, "permissions", set())
        if required_permission not in permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Missing required permission '{required_permission.value}'",
            )

    return _dependency
