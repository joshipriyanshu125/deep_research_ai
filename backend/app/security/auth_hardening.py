"""
Day 53 — Authentication & Authorization Hardening

Provides:
  - Strong password policy validation
  - Timing-safe credential comparisons
  - Role-based authorization utilities (RBAC)
  - Secret management & insecure key detection
"""

from __future__ import annotations

import hmac
import re
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status

from app.config.settings import settings
from app.database.models.user import UserInDB


class UserRole(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    USER = "user"
    GUEST = "guest"


ROLE_HIERARCHY: Dict[UserRole, int] = {
    UserRole.ADMIN: 40,
    UserRole.RESEARCHER: 30,
    UserRole.USER: 20,
    UserRole.GUEST: 10,
}


class PasswordValidator:
    """Enforces enterprise password strength standards."""

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
        """
        Validates:
          - Minimum 8 characters
          - Contains uppercase letter
          - Contains lowercase letter
          - Contains digit
          - Contains special character
        """
        errors = []
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_]", password):
            errors.append("Password must contain at least one special character.")

        return len(errors) == 0, errors


class SecretManager:
    """Assesses secret security, prevents default secret leaks in production."""

    INSECURE_SECRETS = {
        "supersecretjwtkey_change_in_production_deep_research_ai",
        "secret",
        "changeme",
        "default_secret",
        "12345678",
    }

    @classmethod
    def is_secret_secure(cls, secret_key: str, environment: str = "production") -> Tuple[bool, str]:
        if not secret_key or len(secret_key) < 16:
            return False, "Secret key must be at least 16 characters long."
        if secret_key in cls.INSECURE_SECRETS and environment == "production":
            return False, "Default or insecure secret key detected in production environment."
        return True, "Secret key is secure."

    @classmethod
    def mask_secret(cls, secret: str, visible_chars: int = 4) -> str:
        """Safely masks a secret string for logs/diagnostics."""
        if not secret or len(secret) <= visible_chars:
            return "***"
        return f"{secret[:visible_chars]}...[MASKED]"


class AuthorizationManager:
    """Role-based authorization verifier."""

    @staticmethod
    def require_minimum_role(user: UserInDB, required_role: UserRole) -> bool:
        """Checks whether the user holds at least the required role level."""
        user_role_str = getattr(user, "role", "user") or "user"
        try:
            user_role = UserRole(user_role_str)
        except ValueError:
            user_role = UserRole.USER

        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires '{required_role.value}' role or higher.",
            )
        return True

    @staticmethod
    def timing_safe_compare(val_a: str, val_b: str) -> bool:
        """Prevents timing attacks when comparing sensitive tokens or hashes."""
        return hmac.compare_digest(val_a.encode("utf-8"), val_b.encode("utf-8"))


password_validator = PasswordValidator()
secret_manager = SecretManager()
auth_manager = AuthorizationManager()
