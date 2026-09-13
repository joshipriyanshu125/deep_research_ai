"""
Day 55 — SSRF (Server-Side Request Forgery) Protection

Protects the backend fetcher against malicious URL targets:
  - http://localhost
  - http://127.0.0.1
  - http://169.254.169.254 (Cloud metadata service)
  - 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 (Private subnets)
  - Non-HTTP protocols (file://, ftp://, gopher://, dict://, data:, ldap://)
  - DNS resolution validation (blocks DNS rebinding / hostnames resolving to private IPs)
  - Redirect target validation
  - Strict connection/read timeouts & response size limits
"""

from __future__ import annotations

import socket
import ipaddress
import urllib.parse
from typing import List, Optional, Tuple, Set
import logging

logger = logging.getLogger("deep_research.security.ssrf")


class SSRFValidationError(ValueError):
    """Raised when a URL violates SSRF safety constraints."""
    pass



# Private, loopback, link-local and reserved IP networks (IPv4 and IPv6)
BLOCKED_NETWORKS = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # Private A
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (Carrier-grade NAT)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link Local / AWS/GCP/Azure Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # Private B
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.168.0.0/16"),     # Private C
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),    # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),     # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved for Future Use
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped IPv6
    ipaddress.ip_network("100::/64"),           # Discard prefix
    ipaddress.ip_network("64:ff9b::/96"),       # IPv4/IPv6 translation
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
]

ALLOWED_SCHEMES: Set[str] = {"http", "https"}
ALLOWED_PORTS: Set[int] = {80, 443, 8000, 8080, 8443, 8888, 3000, 5000}


class SSRFProtector:
    """
    Day 55 — Comprehensive SSRF Shield.
    Validates URLs, IP addresses, redirect targets, and protocol limits
    before any HTTP request is dispatched.
    """

    def __init__(
        self,
        allow_private_ips: bool = False,
        allowed_schemes: Optional[Set[str]] = None,
        max_response_size_bytes: int = 10 * 1024 * 1024,  # 10 MB default limit
        default_timeout_seconds: float = 12.0,
    ):
        self.allow_private_ips = allow_private_ips
        self.allowed_schemes = allowed_schemes or ALLOWED_SCHEMES
        self.max_response_size_bytes = max_response_size_bytes
        self.default_timeout_seconds = default_timeout_seconds

    def is_ip_blocked(self, ip_str: str) -> bool:
        """
        Tests whether an IP address belongs to private, loopback, link-local,
        or metadata networks.
        """
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return True  # Invalid IP representation is blocked

        # Check for IPv4 mapped IPv6 (e.g. ::ffff:127.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped

        # Standard checks
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return True

        # Explicit blocked subnet check
        for net in BLOCKED_NETWORKS:
            try:
                if ip in net:
                    return True
            except TypeError:
                continue

        return False

    def resolve_and_validate_hostname(self, hostname: str) -> List[str]:
        """
        Resolves hostname to IP addresses via DNS and validates that ALL resolved
        addresses are public and safe from SSRF.
        """
        if not hostname:
            raise SSRFValidationError("Hostname cannot be empty.")

        hostname_clean = hostname.strip().lower()

        # Immediate check for common loopback/metadata hostnames
        if hostname_clean in {
            "localhost",
            "localhost.localdomain",
            "metadata.google.internal",
            "instance-data",
            "169.254.169.254",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
        }:
            raise SSRFValidationError(f"Target hostname '{hostname_clean}' is blocked (loopback/internal service).")

        # Attempt to parse directly as an IP address
        try:
            ip_obj = ipaddress.ip_address(hostname_clean)
            if not self.allow_private_ips and self.is_ip_blocked(str(ip_obj)):
                raise SSRFValidationError(f"Direct IP target '{hostname_clean}' is in a private/blocked range.")
            return [str(ip_obj)]
        except ValueError:
            pass

        # Perform DNS resolution
        try:
            addr_info = socket.getaddrinfo(hostname_clean, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            resolved_ips: List[str] = []
            for item in addr_info:
                sockaddr = item[4]
                ip_addr = sockaddr[0]
                if ip_addr not in resolved_ips:
                    resolved_ips.append(ip_addr)

            if not resolved_ips:
                raise SSRFValidationError(f"Could not resolve hostname '{hostname_clean}'.")

            if not self.allow_private_ips:
                for ip in resolved_ips:
                    if self.is_ip_blocked(ip):
                        raise SSRFValidationError(
                            f"Hostname '{hostname_clean}' resolved to blocked/private IP '{ip}'."
                        )

            return resolved_ips

        except socket.gaierror as e:
            raise SSRFValidationError(f"DNS resolution failure for '{hostname_clean}': {e}")
        except Exception as e:
            if isinstance(e, SSRFValidationError):
                raise
            raise SSRFValidationError(f"Error validating hostname '{hostname_clean}': {e}")

    def validate_url(self, url: str) -> str:
        """
        Comprehensive URL validation for SSRF defense:
          - Scheme validation (http/https only)
          - No embedded credentials (http://user:pass@host)
          - Hostname validation & DNS resolution
          - Port restrictions
        Returns the sanitized URL if valid, or raises SSRFValidationError.
        """
        if not url or not isinstance(url, str):
            raise SSRFValidationError("URL must be a non-empty string.")

        url_clean = url.strip()
        try:
            parsed_initial = urllib.parse.urlsplit(url_clean)
        except Exception as e:
            raise SSRFValidationError(f"Malformed URL structure: {e}")

        if not parsed_initial.scheme:
            url_clean = "https://" + url_clean
            try:
                parsed = urllib.parse.urlsplit(url_clean)
            except Exception as e:
                raise SSRFValidationError(f"Malformed URL structure: {e}")
        else:
            parsed = parsed_initial

        # 1. Scheme check
        scheme = parsed.scheme.lower()
        if scheme not in self.allowed_schemes:
            raise SSRFValidationError(
                f"Invalid URL protocol '{scheme}'. Allowed protocols are: {', '.join(sorted(self.allowed_schemes))}."
            )

        # 2. Check for embedded userinfo (user:pass@host)
        if parsed.username or parsed.password:
            raise SSRFValidationError("URLs with embedded authentication credentials are not permitted.")

        # 3. Host validation
        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("URL does not contain a valid hostname.")

        # 4. Port validation
        try:
            port = parsed.port
            if port and port not in ALLOWED_PORTS:
                raise SSRFValidationError(f"Port {port} is not in the allowed outbound port list.")
        except ValueError:
            raise SSRFValidationError("Invalid port specification in URL.")

        # 5. Resolve and validate IP
        self.resolve_and_validate_hostname(hostname)

        return url_clean


    def validate_redirect(self, original_url: str, redirect_target: str) -> str:
        """
        Validates a redirect target to prevent open redirect -> SSRF attack chains.
        """
        # Resolve relative redirect URLs against the original URL
        target_absolute = urllib.parse.urljoin(original_url, redirect_target)
        return self.validate_url(target_absolute)

    def is_safe_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """Non-throwing safe URL check. Returns (is_safe, error_message)."""
        try:
            self.validate_url(url)
            return True, None
        except SSRFValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected validation failure: {e}"


ssrf_protector = SSRFProtector()


def validate_url_safe(url: str, allow_private: bool = False) -> str:
    """Convenience helper to validate a URL against SSRF constraints."""
    protector = SSRFProtector(allow_private_ips=allow_private)
    return protector.validate_url(url)
