"""
Security package initialization for Days 53–55:
  - Day 53: Security hardening (input validation, headers, rate limiting, request size, logging filter, secret management)
  - Day 54: Prompt injection protection & untrusted data isolation
  - Day 55: SSRF protection, IP filtering, protocol enforcement
"""

from app.security.ssrf import (
    SSRFProtector,
    SSRFValidationError,
    validate_url_safe,
    ssrf_protector,
)
from app.security.prompt_injection import (
    PromptInjectionGuard,
    InjectionScanResult,
    prompt_injection_guard,
)
from app.security.sanitizer import (
    InputValidator,
    HTMLSanitizer,
    input_validator,
    html_sanitizer,
)
from app.security.headers import SecureHeadersMiddleware, DEFAULT_SECURITY_HEADERS
from app.security.request_size import RequestSizeLimitMiddleware
from app.security.logging_filter import SensitiveDataFilter, redact_sensitive_data
from app.security.auth_hardening import (
    UserRole,
    PasswordValidator,
    SecretManager,
    AuthorizationManager,
    password_validator,
    secret_manager,
    auth_manager,
)

__all__ = [
    "SSRFProtector",
    "SSRFValidationError",
    "validate_url_safe",
    "ssrf_protector",
    "PromptInjectionGuard",
    "InjectionScanResult",
    "prompt_injection_guard",
    "InputValidator",
    "HTMLSanitizer",
    "input_validator",
    "html_sanitizer",
    "SecureHeadersMiddleware",
    "DEFAULT_SECURITY_HEADERS",
    "RequestSizeLimitMiddleware",
    "SensitiveDataFilter",
    "redact_sensitive_data",
    "UserRole",
    "PasswordValidator",
    "SecretManager",
    "AuthorizationManager",
    "password_validator",
    "secret_manager",
    "auth_manager",
]
