"""Tests for secret detection, sensitive path identification, and redaction."""

from pathlib import Path
from aapa.secret_filter import (
    contains_secrets,
    is_sensitive_path,
    redact_secrets,
    sanitize_dict,
)


def test_contains_secrets():
    # AWS key
    has_sec, types = contains_secrets("export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
    assert has_sec
    assert "AWS_ACCESS_KEY" in types

    # GitHub PAT
    has_sec, types = contains_secrets("git clone https://ghp_123456789012345678901234567890123456@github.com/repo")
    assert has_sec
    assert "GITHUB_TOKEN" in types

    # Private key
    sample_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
    has_sec, types = contains_secrets(sample_key)
    assert has_sec
    assert "PRIVATE_KEY" in types

    # Safe text
    has_sec, types = contains_secrets("pytest tests/ -v")
    assert not has_sec
    assert len(types) == 0


def test_redact_secrets():
    raw = "Connecting with AKIAIOSFODNN7EXAMPLE and token ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    redacted = redact_secrets(raw)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in redacted
    assert "[REDACTED_AWS_ACCESS_KEY]" in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted


def test_is_sensitive_path():
    assert is_sensitive_path(".env")
    assert is_sensitive_path(".env.local")
    assert is_sensitive_path(".env.production")
    assert is_sensitive_path("id_rsa")
    assert is_sensitive_path("id_ed25519")
    assert is_sensitive_path("credentials.json")
    assert is_sensitive_path("secrets.json")
    assert is_sensitive_path("server.key")
    assert is_sensitive_path("cert.pem")
    assert is_sensitive_path("C:\\Users\\user\\.aws\\credentials")

    # Non-sensitive paths
    assert not is_sensitive_path("README.md")
    assert not is_sensitive_path("src/main.py")
    assert not is_sensitive_path("package.json")
    assert not is_sensitive_path("pyproject.toml")


def test_sanitize_dict():
    data = {
        "command": "echo AKIAIOSFODNN7EXAMPLE",
        "nested": {
            "token": "ghp_123456789012345678901234567890123456",
            "safe": "hello"
        },
        "list_items": ["echo AKIAIOSFODNN7EXAMPLE", "safe string"]
    }
    cleaned = sanitize_dict(data)
    assert "AKIAIOSFODNN7EXAMPLE" not in str(cleaned)
    assert "[REDACTED_AWS_ACCESS_KEY]" in cleaned["command"]
    assert "[REDACTED_GITHUB_TOKEN]" in cleaned["nested"]["token"]
    assert cleaned["nested"]["safe"] == "hello"
