"""
Security management for workflow server.
"""

import time
from typing import Any

try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


class SecurityManager:
    """Manages security boundaries and access control."""

    def __init__(self):
        self.contexts = {}

    def validate_context(self, security_context: dict[str, Any]) -> bool:
        """Validate security context."""
        return "tenant_id" in security_context and "user_id" in security_context


class ResourceAccessControl:
    """Manages resource access control policies."""

    def __init__(self):
        self.policies = {}

    def load_policies(self, policies: dict[str, Any]):
        """Load access control policies."""
        self.policies = policies

    def check_access(self, role: str, resource: str, action: str) -> bool:
        """Check if role has access to perform action on resource."""
        if resource not in self.policies:
            return False

        if action not in self.policies[resource]:
            return False

        allowed_roles = self.policies[resource][action]
        return role in allowed_roles


class AuthenticationManager:
    """Manages authentication and token generation."""

    def __init__(self, provider: str = "jwt", secret_key: str = "secret"):
        self.provider = provider
        self.secret_key = secret_key

    def generate_token(self, user_info: dict[str, Any], expiry_seconds: int = 3600) -> str:
        """Generate authentication token."""
        if not JWT_AVAILABLE:
            raise ImportError("JWT library not available. Install with: pip install PyJWT")

        payload = user_info.copy()
        payload["exp"] = time.time() + expiry_seconds
        payload["iat"] = time.time()

        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate authentication token."""
        if not JWT_AVAILABLE:
            raise ImportError("JWT library not available. Install with: pip install PyJWT")

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # Check expiration
            if "exp" in payload and payload["exp"] < time.time():
                return None

            return payload
        except Exception:
            return None
