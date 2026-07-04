"""Tests for the AI Manifest fetcher + parser (Phase 5 commit 28).

Coverage matrix:
  * parse_ai_manifest: known fields populate correctly; unknown fields
    round-trip to ``extra``; non-object payloads raise AiManifestError;
    missing optional fields are tolerated
  * fetch_ai_manifest:
    - 200 + valid JSON → AiManifest
    - 404 → None
    - 5xx → None
    - oversize body → None (with warning)
    - invalid JSON → None
    - non-object JSON → None
    - timeout / network error → None
    - empty base_url → None (no fetch attempted)
  * Endpoint helpers: ``endpoint_for(name)`` resolves; ``has_endpoints``
"""

from __future__ import annotations

import json

import pytest

from cli_agent_orchestrator.web import (
    AiManifestError,
    fetch_ai_manifest,
    parse_ai_manifest,
)

# ---------------------------------------------------------------------------
# parse_ai_manifest
# ---------------------------------------------------------------------------


class TestParseManifest:
    def test_known_fields_populate(self):
        payload = {
            "name": "Example",
            "description": "A test site",
            "version": "1.0.0",
            "base_url": "https://example.com",
            "endpoints": [{"name": "search", "url": "/search", "method": "GET"}],
            "rate_limit": {"requests_per_minute": 60},
            "contact": {"email": "abuse@example.com"},
            "schemas": {"product": {"type": "object"}},
        }
        manifest = parse_ai_manifest(payload)
        assert manifest.name == "Example"
        assert manifest.description == "A test site"
        assert manifest.version == "1.0.0"
        assert manifest.base_url == "https://example.com"
        assert manifest.rate_limit == {"requests_per_minute": 60}
        assert manifest.contact == {"email": "abuse@example.com"}
        assert manifest.schemas == {"product": {"type": "object"}}

    def test_unknown_fields_land_in_extra(self):
        payload = {"name": "x", "experimental_feature": [1, 2, 3]}
        manifest = parse_ai_manifest(payload)
        assert manifest.extra["experimental_feature"] == [1, 2, 3]

    def test_missing_optional_fields_tolerated(self):
        manifest = parse_ai_manifest({"name": "minimal"})
        assert manifest.name == "minimal"
        assert manifest.description == ""
        assert manifest.endpoints == []
        assert manifest.contact == {}

    def test_non_object_payload_raises(self):
        with pytest.raises(AiManifestError):
            parse_ai_manifest([1, 2, 3])

    def test_string_payload_raises(self):
        with pytest.raises(AiManifestError):
            parse_ai_manifest("not an object")


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------


class TestEndpointHelpers:
    def test_has_endpoints_true_when_present(self):
        manifest = parse_ai_manifest({"endpoints": [{"name": "x"}]})
        assert manifest.has_endpoints is True

    def test_has_endpoints_false_when_empty(self):
        manifest = parse_ai_manifest({})
        assert manifest.has_endpoints is False

    def test_endpoint_for_resolves(self):
        manifest = parse_ai_manifest(
            {"endpoints": [{"name": "search", "url": "/s"}, {"name": "buy", "url": "/b"}]}
        )
        assert manifest.endpoint_for("search") == {"name": "search", "url": "/s"}

    def test_endpoint_for_unknown_returns_none(self):
        manifest = parse_ai_manifest({"endpoints": [{"name": "search"}]})
        assert manifest.endpoint_for("nope") is None


# ---------------------------------------------------------------------------
# fetch_ai_manifest
# ---------------------------------------------------------------------------


def _stub_fetcher(status: int, body: bytes):
    captured: dict[str, str] = {}

    def fetch(url: str, timeout: float) -> tuple[int, bytes]:
        captured["url"] = url
        captured["timeout"] = timeout
        return status, body

    fetch.captured = captured  # type: ignore[attr-defined]
    return fetch


class TestFetchManifest:
    def test_success_returns_parsed_manifest(self):
        body = json.dumps({"name": "Example"}).encode("utf-8")
        manifest = fetch_ai_manifest("https://example.com", fetcher=_stub_fetcher(200, body))
        assert manifest is not None
        assert manifest.name == "Example"

    def test_404_returns_none(self):
        manifest = fetch_ai_manifest("https://example.com", fetcher=_stub_fetcher(404, b""))
        assert manifest is None

    def test_5xx_returns_none(self):
        manifest = fetch_ai_manifest("https://example.com", fetcher=_stub_fetcher(500, b"oops"))
        assert manifest is None

    def test_invalid_json_returns_none(self):
        manifest = fetch_ai_manifest("https://example.com", fetcher=_stub_fetcher(200, b"not json"))
        assert manifest is None

    def test_non_object_json_returns_none(self):
        manifest = fetch_ai_manifest(
            "https://example.com", fetcher=_stub_fetcher(200, b"[1, 2, 3]")
        )
        assert manifest is None

    def test_oversize_body_returns_none(self):
        # 2 MiB — over the 1 MiB cap.
        oversize = b"x" * (2 * 1024 * 1024)
        manifest = fetch_ai_manifest("https://example.com", fetcher=_stub_fetcher(200, oversize))
        assert manifest is None

    def test_network_error_returns_none(self):
        def boom(url: str, timeout: float) -> tuple[int, bytes]:
            raise OSError("connection refused")

        manifest = fetch_ai_manifest("https://example.com", fetcher=boom)
        assert manifest is None

    def test_empty_base_url_returns_none_without_fetch(self):
        called = []

        def fetcher(url: str, timeout: float) -> tuple[int, bytes]:
            called.append(url)
            return 200, b"{}"

        assert fetch_ai_manifest("", fetcher=fetcher) is None
        assert called == []  # Never attempted.

    def test_well_known_path_appended(self):
        fetcher = _stub_fetcher(200, b'{"name": "x"}')
        fetch_ai_manifest("https://example.com", fetcher=fetcher)
        assert fetcher.captured["url"] == "https://example.com/.well-known/ai-manifest.json"

    def test_trailing_slash_handled(self):
        fetcher = _stub_fetcher(200, b'{"name": "x"}')
        fetch_ai_manifest("https://example.com/", fetcher=fetcher)
        assert fetcher.captured["url"] == "https://example.com/.well-known/ai-manifest.json"

    def test_timeout_passed_through(self):
        fetcher = _stub_fetcher(200, b'{"name": "x"}')
        fetch_ai_manifest("https://example.com", timeout_seconds=0.5, fetcher=fetcher)
        assert fetcher.captured["timeout"] == 0.5
