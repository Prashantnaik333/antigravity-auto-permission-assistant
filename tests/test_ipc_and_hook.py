"""Integration tests for IPC server and Antigravity hook workflow."""

import json
import time
import urllib.request
from aapa.config import PolicyConfig
from aapa.hook import evaluate_standalone
from aapa.ipc_server import AAPAIPCServer
from aapa.risk_analyzer import RiskAnalyzer


def test_hook_evaluate_standalone():
    # Safe read-only hook payload
    safe_payload = {
        "conversationId": "conv-test",
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": "dir",
                "Cwd": "C:/Projects"
            }
        }
    }
    resp = evaluate_standalone(safe_payload)
    assert resp["decision"] == "allow"

    # Blocked hook payload
    blocked_payload = {
        "conversationId": "conv-test",
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": "rm -rf /",
                "Cwd": "C:/Projects"
            }
        }
    }
    resp_blocked = evaluate_standalone(blocked_payload)
    assert resp_blocked["decision"] == "deny"


def test_ipc_server_lifecycle():
    policy = PolicyConfig()
    analyzer = RiskAnalyzer(policy=policy)

    # Use a high random test port
    test_port = 49199
    server = AAPAIPCServer(("127.0.0.1", test_port), analyzer=analyzer)
    server.start_background()

    try:
        # 1. Health check
        health_url = f"http://127.0.0.1:{test_port}/api/health"
        req = urllib.request.Request(health_url)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "online"

        # 2. Evaluate auto-approved command
        eval_url = f"http://127.0.0.1:{test_port}/api/evaluate"
        post_data = json.dumps({
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "ls",
                    "Cwd": "C:/Projects"
                }
            }
        }).encode("utf-8")

        req2 = urllib.request.Request(eval_url, data=post_data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req2, timeout=3.0) as resp2:
            data2 = json.loads(resp2.read().decode("utf-8"))
            assert data2["decision"] == "allow"

    finally:
        server.stop()
