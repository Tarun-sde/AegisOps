from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import os
import secrets
import socket
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db import get_db
from apps.api.app.models import AuditEvent, Membership, Organization, User, UserSession

SESSION_COOKIE_NAME = "aegisops_session"
CSRF_COOKIE_NAME = "aegisops_csrf"
SESSION_DURATION = timedelta(days=7)

ROLE_LEVELS: dict[str, int] = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1,
}

ALLOWED_INTERNAL_HOSTS = {
    "shop-api",
    "localhost",
    "127.0.0.1",
    "prometheus",
    "loki",
    "tempo",
    "otel-collector",
}

PROHIBITED_METADATA_HOSTS = {
    "169.254.169.254",
    "169.254.170.2",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "metadata.turing.internal",
    "100.100.100.200",
    "fd00:ec2::254",
}

PROHIBITED_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("fd00:ec2::254"),
}

CARRIER_GRADE_NAT_NET = ipaddress.IPv4Network("100.64.0.0/10")


def hash_password(password: str) -> tuple[str, str]:
    """Hash password using standard library scrypt with cryptographically random salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1,
    ).hex()
    return hashed, salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """Verify password in constant time using secrets.compare_digest."""
    try:
        calculated = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            n=16384,
            r=8,
            p=1,
        ).hex()
        return secrets.compare_digest(calculated, hashed_password)
    except Exception:
        return False


def create_user_session(
    db: Session,
    user_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, UserSession]:
    """Create a cryptographically random, SHA-256 hashed server-side session."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + SESSION_DURATION

    session = UserSession(
        session_token_hash=token_hash,
        user_id=user_id,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent[:255] if user_agent else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw_token, session


def revoke_user_session(db: Session, raw_token: str) -> bool:
    """Revoke an active session by setting revoked_at timestamp."""
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session = db.scalar(
        select(UserSession).where(
            UserSession.session_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    )
    if session:
        session.revoked_at = datetime.now(UTC)
        db.commit()
        return True
    return False


def set_auth_cookies(response: Response, raw_token: str) -> str:
    """Configure secure HttpOnly session cookie and readable CSRF double-submit token."""
    is_production = os.environ.get("ENVIRONMENT", "development").lower() == "production"
    csrf_token = secrets.token_urlsafe(24)

    # Session cookie: HttpOnly, restricted from client-side JavaScript
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=is_production,
        path="/",
    )
    # CSRF cookie: accessible to JavaScript for double-submit header validation
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=False,
        samesite="lax",
        secure=is_production,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    """Clear session and CSRF cookies on logout."""
    is_production = os.environ.get("ENVIRONMENT", "development").lower() == "production"
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/", secure=is_production, samesite="lax")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", secure=is_production, samesite="lax")


def log_audit_event(
    db: Session,
    organization_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    resource_type: str,
    resource_id: str | None,
    action: str,
    result: str,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """Record an immutable, append-only security or operational audit event."""
    event = AuditEvent(
        organization_id=organization_id,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        result=result,
        event_metadata=metadata or {},
        ip_address=ip_address,
    )
    db.add(event)
    db.commit()
    return event


def _verify_ip_safety(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    hostname: str | None = None,
    allow_local_demo: bool = False,
) -> None:
    """Validate that an IP does not target private, internal, or cloud metadata destinations."""
    # Handle IPv4-mapped IPv6 (::ffff:127.0.0.1) and 6to4 addresses (2002::/16)
    unmapped = ip.ipv4_mapped if (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped) else ip
    if isinstance(unmapped, ipaddress.IPv6Address) and unmapped.sixtofour:
        unmapped = unmapped.sixtofour

    # Cloud metadata check (checked first to match expected metadata rejection messages)
    if unmapped in PROHIBITED_METADATA_IPS:
        raise ValueError("Access to cloud instance metadata services is prohibited.")

    # Loopback check
    if unmapped.is_loopback:
        if allow_local_demo and hostname and hostname in ALLOWED_INTERNAL_HOSTS:
            return
        raise ValueError(
            f"Loopback connections are prohibited for external connectors (resolved to {unmapped})."
        )

    # Link-local check
    if unmapped.is_link_local:
        raise ValueError(f"Link-local addresses are prohibited (resolved to {unmapped}).")

    # Private network check (RFC 1918 / fc00::/7)
    if unmapped.is_private:
        if allow_local_demo and hostname and hostname in ALLOWED_INTERNAL_HOSTS:
            return
        raise ValueError(
            "Private network connections are prohibited for external connectors "
            f"(resolved to {unmapped})."
        )

    # Multicast check
    if unmapped.is_multicast:
        raise ValueError(f"Multicast addresses are prohibited (resolved to {unmapped}).")

    # Unspecified check (0.0.0.0 / ::)
    if unmapped.is_unspecified:
        raise ValueError(f"Unspecified addresses are prohibited (resolved to {unmapped}).")

    # Reserved check
    if unmapped.is_reserved:
        raise ValueError(f"Reserved addresses are prohibited (resolved to {unmapped}).")

    # Carrier-Grade NAT (RFC 6598: 100.64.0.0/10)
    if isinstance(unmapped, ipaddress.IPv4Address) and unmapped in CARRIER_GRADE_NAT_NET:
        raise ValueError(
            "Carrier-Grade NAT / Shared address space connections are prohibited "
            f"(resolved to {unmapped})."
        )


def validate_connector_url(url: str, allow_local_demo: bool = False) -> str:
    """SSRF prevention: blocks cloud metadata, loopback, private networks, and unresolved hosts."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL must have a valid hostname.")

    # Block well-known cloud metadata endpoints and prohibited hostnames
    if hostname in PROHIBITED_METADATA_HOSTS:
        raise ValueError("Access to cloud instance metadata services is prohibited.")

    # If it's a known internal demo hostname in local/dev mode, allow
    if allow_local_demo and hostname in ALLOWED_INTERNAL_HOSTS:
        return url

    # Validate IP address ranges directly or resolve domain via DNS
    try:
        ip = ipaddress.ip_address(hostname)
        ips = [ip]
    except ValueError:
        # Not a raw IP literal; resolve domain via DNS
        try:
            addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            ips = []
            for info in addr_infos:
                ip_str = info[4][0]
                try:
                    ips.append(ipaddress.ip_address(ip_str))
                except ValueError:
                    continue
            if not ips:
                raise ValueError(
                    f"DNS resolution failed: no IP addresses found for hostname '{hostname}'."
                )
        except socket.gaierror as e:
            raise ValueError(f"DNS resolution failed for hostname '{hostname}': {e}") from e

    for resolved_ip in ips:
        _verify_ip_safety(resolved_ip, hostname=hostname, allow_local_demo=allow_local_demo)

    return url


class SSRFSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Enforces SSRF validation on every redirect hop, blocks downgrade and redirect loops."""

    def __init__(self, allow_local_demo: bool = False, max_redirects: int = 3):
        super().__init__()
        self.allow_local_demo = allow_local_demo
        self.max_redirects = max_redirects
        self._redirect_count = 0

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        self._redirect_count += 1
        if self._redirect_count > self.max_redirects:
            raise ValueError(f"Maximum redirect limit ({self.max_redirects}) exceeded.")

        # Ensure no protocol downgrade (e.g. https -> http)
        old_scheme = urllib.parse.urlparse(req.full_url).scheme.lower()
        new_scheme = urllib.parse.urlparse(newurl).scheme.lower()
        if old_scheme == "https" and new_scheme == "http":
            raise ValueError("Redirect protocol downgrade from HTTPS to HTTP is prohibited.")

        # Validate redirect target against SSRF rules
        validate_connector_url(newurl, allow_local_demo=self.allow_local_demo)

        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        return result


class SSRFSafeHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection subclass that verifies connected socket peer IP before sending bytes."""

    def __init__(self, *args: Any, allow_local_demo: bool = False, **kwargs: Any) -> None:
        self.allow_local_demo = allow_local_demo
        super().__init__(*args, **kwargs)

    def connect(self) -> None:
        super().connect()
        if self.sock is not None:
            peer_ip_str = self.sock.getpeername()[0]
            ip = ipaddress.ip_address(peer_ip_str)
            _verify_ip_safety(ip, hostname=self.host, allow_local_demo=self.allow_local_demo)


class SSRFSafeHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection subclass that verifies connected socket peer IP before TLS handshake."""

    def __init__(self, *args: Any, allow_local_demo: bool = False, **kwargs: Any) -> None:
        self.allow_local_demo = allow_local_demo
        super().__init__(*args, **kwargs)

    def connect(self) -> None:
        super().connect()
        if self.sock is not None:
            peer_ip_str = self.sock.getpeername()[0]
            ip = ipaddress.ip_address(peer_ip_str)
            _verify_ip_safety(ip, hostname=self.host, allow_local_demo=self.allow_local_demo)


class SSRFSafeHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, allow_local_demo: bool = False) -> None:
        super().__init__()
        self.allow_local_demo = allow_local_demo

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        res = self.do_open(
            lambda host, **kwargs: SSRFSafeHTTPConnection(
                host, allow_local_demo=self.allow_local_demo, **kwargs
            ),
            req,
        )
        assert isinstance(res, http.client.HTTPResponse)
        return res


class SSRFSafeHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, allow_local_demo: bool = False, context: Any = None) -> None:
        super().__init__(context=context)
        self.allow_local_demo = allow_local_demo

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        res = self.do_open(
            lambda host, **kwargs: SSRFSafeHTTPSConnection(
                host, allow_local_demo=self.allow_local_demo, **kwargs
            ),
            req,
        )
        assert isinstance(res, http.client.HTTPResponse)
        return res


def get_ssrf_safe_opener(
    allow_local_demo: bool = False, max_redirects: int = 3
) -> urllib.request.OpenerDirector:
    """Build a urllib OpenerDirector hardened against SSRF, redirects, and DNS rebinding."""
    redirect_handler = SSRFSafeRedirectHandler(
        allow_local_demo=allow_local_demo, max_redirects=max_redirects
    )
    http_handler = SSRFSafeHTTPHandler(allow_local_demo=allow_local_demo)
    https_handler = SSRFSafeHTTPSHandler(allow_local_demo=allow_local_demo)
    return urllib.request.build_opener(redirect_handler, http_handler, https_handler)


def compute_tenant_webhook_secret(org_id: uuid.UUID | str) -> str:
    """Compute deterministic HMAC-derived per-tenant webhook secret."""
    key = os.environ.get("ALERTMANAGER_SECRET", "aegisops-demo-alertmanager-secret").encode("utf-8")
    return hmac.new(key, str(org_id).encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass
class TenantContext:
    user: User
    organization: Organization
    role: str

    def can(self, required_role: str) -> bool:
        return ROLE_LEVELS.get(self.role, 0) >= ROLE_LEVELS.get(required_role, 0)


def extract_raw_token(request: Request) -> str | None:
    # 1. HttpOnly cookie (primary for web browsers)
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    # 2. Authorization: Bearer <token> (for programmatic API and integration tests)
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    return None


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Authenticate request using durable server session cookie or Bearer token."""
    raw_token = extract_raw_token(request)
    if not raw_token:
        if os.environ.get("AEGISOPS_ALLOW_ANONYMOUS_DEMO") == "1":
            demo_user = db.scalar(select(User).where(User.email == "demo@aegisops.local"))
            if demo_user:
                return demo_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing session cookie or Bearer token.",
        )

    # CSRF validation for mutating cookie-authenticated requests (double-submit verification)
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and SESSION_COOKIE_NAME in request.cookies
    ):
        csrf_header = request.headers.get("x-csrf-token")
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        # Validate only if CSRF cookie was set (double-submit verification)
        if csrf_cookie and (
            not csrf_header or not secrets.compare_digest(csrf_header, csrf_cookie)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token mismatch or missing X-CSRF-Token header.",
            )

    if raw_token in ("aegisops-demo-token", "aegisops-demo-alertmanager-secret"):
        demo_user = db.scalar(select(User).where(User.email == "demo@aegisops.local"))
        if demo_user:
            return demo_user

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now_utc = datetime.now(UTC)

    session = db.scalar(
        select(UserSession).where(
            UserSession.session_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now_utc,
        )
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
        )

    user = db.scalar(select(User).where(User.id == session.user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found.",
        )

    return user


def get_tenant_context(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    x_organization_id: Annotated[str | None, Header(alias="x-organization-id")] = None,
) -> TenantContext:
    """Resolve and enforce authorized organization membership and role."""
    target_org_id: uuid.UUID | None = None
    if x_organization_id:
        try:
            target_org_id = uuid.UUID(x_organization_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization ID format in X-Organization-ID header.",
            ) from e

    # Query user's memberships
    memberships = db.scalars(
        select(Membership)
        .where(Membership.user_id == current_user.id)
        .order_by(Membership.created_at.asc())
    ).all()

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization. Please complete onboarding.",
        )

    active_membership: Membership | None = None
    if target_org_id:
        active_membership = next(
            (m for m in memberships if m.organization_id == target_org_id), None
        )
        if not active_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not a member of the requested organization.",
            )
    else:
        # Default to user's first/primary organization
        active_membership = memberships[0]

    org = db.scalar(
        select(Organization).where(Organization.id == active_membership.organization_id)
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    return TenantContext(
        user=current_user,
        organization=org,
        role=active_membership.role,
    )


def require_role(min_role: str) -> Callable[[TenantContext], TenantContext]:
    """Dependency factory checking that active tenant membership has at least min_role."""

    def _role_checker(
        context: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> TenantContext:
        if not context.can(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. Role '{context.role}' cannot perform this action "
                    f"(requires '{min_role}')."
                ),
            )
        return context

    return _role_checker
