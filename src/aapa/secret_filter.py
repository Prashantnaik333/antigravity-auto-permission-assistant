"""Sensitive data filtering and redaction module for AAPA.

Guarantees that credentials, tokens, private keys, and sensitive environment variables
are never logged, displayed unredacted, or passed to external AI services.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

SECRET_PATTERNS = [
    # AWS Access Key
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "AWS_ACCESS_KEY"),
    # AWS Secret Key
    (re.compile(r"(?i)\baws[_\s-]?secret[_\s-]?access[_\s-]?key[\s:=]+['\"]?([a-zA-Z0-9/+=]{40})['\"]?"), "AWS_SECRET_KEY"),
    # GitHub Personal Access Token (classic & fine-grained)
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,255})\b"), "GITHUB_TOKEN"),
    (re.compile(r"\b(github_pat_[A-Za-z0-9_]{82})\b"), "GITHUB_FINE_GRAINED_TOKEN"),
    # Google API Key
    (re.compile(r"\b(AIza[0-9A-Za-z\-_]{35})\b"), "GOOGLE_API_KEY"),
    # Slack Token
    (re.compile(r"\b(xox[baprs]-[0-9a-zA-Z-]{10,72})\b"), "SLACK_TOKEN"),
    # Generic Private Key
    (re.compile(r"-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE KEY[\s\S]*?-----END\s+(?:RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE KEY-----"), "PRIVATE_KEY"),
    # OpenSSH single line private key pattern
    (re.compile(r"\bOPENSSH PRIVATE KEY\b"), "OPENSSH_KEY"),
    # Database Connection URIs with credentials
    (re.compile(r"(?i)\b(postgres|postgresql|mysql|mongodb|redis|mssql):\/\/([^:]+):([^@]+)@"), "DB_PASSWORD"),
    # Generic Bearer Tokens
    (re.compile(r"(?i)bearer\s+([a-zA-Z0-9\-_]{24,})"), "BEARER_TOKEN"),
    # Generic API Key / Secret assignments
    (re.compile(r"(?i)\b(api_key|apikey|secret_key|client_secret|access_token|auth_token)\s*[:=]\s*['\"]?([a-zA-Z0-9\-_]{16,})['\"]?"), "GENERIC_SECRET"),
]

SENSITIVE_FILENAME_PATTERNS = [
    re.compile(r"(?i)(^|[/\\])\.env(\.[a-z0-9_-]+)?$"),
    re.compile(r"(?i)(^|[/\\])id_(rsa|ed25519|dsa|ecdsa)(\.pub)?$"),
    re.compile(r"(?i)\.(pem|key|pfx|p12|pkcs12|jks|kdbx)$"),
    re.compile(r"(?i)(^|[/\\])(secrets?|credentials|service[_-]account)\.json$"),
    re.compile(r"(?i)(^|[/\\])client_secrets?.*\.json$"),
    re.compile(r"(?i)(^|[/\\])\.aws[/\\]credentials$"),
    re.compile(r"(?i)(^|[/\\])\.azure[/\\]"),
    re.compile(r"(?i)(^|[/\\])\.kube[/\\]config$"),
    re.compile(r"(?i)(^|[/\\])\.npmrc$"),
    re.compile(r"(?i)(^|[/\\])\.pypirc$"),
]


def contains_secrets(text: str) -> Tuple[bool, List[str]]:
    """Checks whether the input text contains recognizable secrets."""
    if not text:
        return False, []
    
    detected: List[str] = []
    for pattern, secret_type in SECRET_PATTERNS:
        if pattern.search(text):
            detected.append(secret_type)
    return len(detected) > 0, detected


def redact_secrets(text: str) -> str:
    """Replaces discovered secrets with a clean redaction placeholder."""
    if not text:
        return text

    sanitized = text
    for pattern, secret_type in SECRET_PATTERNS:
        def _replace_match(match: re.Match) -> str:
            # If the regex has groups, redact the sensitive group or full match
            matched_str = match.group(0)
            if match.lastindex and match.lastindex >= 1:
                secret_part = match.group(match.lastindex)
                return matched_str.replace(secret_part, f"[REDACTED_{secret_type}]")
            return f"[REDACTED_{secret_type}]"

        sanitized = pattern.sub(_replace_match, sanitized)

    return sanitized


def is_sensitive_path(path_str: str | Path) -> bool:
    """Checks if a given file path points to a known credential or secret file."""
    normalized = str(path_str).replace("\\", "/")
    for pattern in SENSITIVE_FILENAME_PATTERNS:
        if pattern.search(normalized):
            return True
    return False


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts secrets in dict values."""
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            sanitized[k] = redact_secrets(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_dict(item) if isinstance(item, dict)
                else (redact_secrets(item) if isinstance(item, str) else item)
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized
