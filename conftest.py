"""Offline tests use synthetic HTTP responses, never developer services (DEC-266)."""

import errno
import json
import socket
import urllib.error
from io import BytesIO
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest


@pytest.fixture(autouse=True)
def isolate_offline_tests(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        yield
        return

    monkeypatch.setenv("AEGISOPS_AGENT_MODE", "offline")
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guard(original):
        def connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                attempts.append(address)
                raise AssertionError("Offline test attempted a network connection")
            return original(sock, address)

        return connect

    monkeypatch.setattr(socket.socket, "connect", guard(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(original_connect_ex))
    yield
    assert not attempts, "Offline test attempted network access; mock its transport"


@pytest.fixture
def telemetry_http(request, monkeypatch):
    """Mock provider wire responses; gateway, ADK and persistence remain real."""
    if request.node.get_closest_marker("integration"):
        return None
    state = getattr(request, "param", "empty")
    assert state in ("supported", "empty", "unavailable")
    monkeypatch.setenv("AEGISOPS_PROM_URL", "http://prometheus.test")
    monkeypatch.setenv("AEGISOPS_LOKI_URL", "http://loki.test")
    metrics = []
    logs = []
    if state == "supported":
        metrics = [{"metric": {}, "value": [1791676800, "0.25"]}]
        logs = [
            {
                "stream": {"service_name": "shop-api", "level": "error"},
                "values": [
                    [
                        "1791676800000000000",
                        json.dumps(
                            {
                                "level": "error",
                                "service": "shop-api",
                                "event": "http_request_error",
                                "message": (
                                    "HTTP 500: checkout payment gateway failure on POST /checkout"
                                ),
                                "error_category": "APPLICATION_EXCEPTION",
                                "error_code": "CHECKOUT_GATEWAY_TIMEOUT",
                                "exception_class": "PaymentGatewayTimeoutException",
                            }
                        ),
                    ]
                ],
            }
        ]

    def respond(req, timeout):
        url = urlsplit(req.full_url)
        assert req.get_method() == "GET"
        assert timeout == 5.0
        if (url.netloc, url.path) == ("prometheus.test", "/api/v1/query"):
            data = {"resultType": "vector", "result": metrics}
        elif (url.netloc, url.path) == ("loki.test", "/loki/api/v1/query_range"):
            data = {"resultType": "streams", "result": logs}
        elif url.netloc == "api.github.com":
            if state == "unavailable":
                raise urllib.error.URLError(
                    ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")
                )
            if "/deployments" in url.path:
                deploy_list = [
                    {
                        "id": 101,
                        "sha": "c0ffee1",
                        "ref": "main",
                        "environment": "staging",
                        "created_at": "2026-10-11T12:00:00Z",
                        "description": "Deploy release v1.4.2",
                    }
                ]
                return BytesIO(json.dumps(deploy_list).encode())
            elif "/commits" in url.path:
                commit_list = [
                    {
                        "sha": "c0ffee1",
                        "commit": {
                            "message": "fix(checkout): update payment retry handler",
                            "author": {"name": "Test Author", "date": "2026-10-11T12:00:00Z"},
                        },
                    }
                ]
                return BytesIO(json.dumps(commit_list).encode())
            return BytesIO(b"[]")
        else:
            pytest.fail("Unexpected telemetry URL")
        if state == "unavailable":
            raise urllib.error.URLError(
                ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")
            )
        return BytesIO(json.dumps({"status": "success", "data": data}).encode())

    transport = Mock(side_effect=respond)
    monkeypatch.setattr("urllib.request.urlopen", transport)
    return transport
