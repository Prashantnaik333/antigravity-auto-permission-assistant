"""Google Antigravity PreToolUse hook entry point for AAPA.

Invoked directly by Google Antigravity via hooks.json. Receives tool call context on stdin
and outputs structured approval decisions to stdout.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

from aapa.config import load_policy, load_settings
from aapa.request_parser import RequestParser
from aapa.risk_analyzer import RiskAnalyzer


def evaluate_via_ipc(payload: Dict[str, Any], host: str = "127.0.0.1", port: int = 49152) -> Dict[str, Any] | None:
    """Attempts to forward the request to the live AAPA Desktop UI IPC server."""
    url = f"http://{host}:{port}/api/evaluate"
    req_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        # IPC server is offline or desktop UI is closed
        return None
    return None


def evaluate_standalone(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates the hook request standalone when the AAPA desktop UI is closed."""
    policy = load_policy()
    analyzer = RiskAnalyzer(policy=policy)
    normalized = RequestParser.parse(payload)
    analysis = analyzer.analyze(normalized)
    return analysis.to_antigravity_hook_response()


def main() -> None:
    """Standard I/O hook entrypoint."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            # No input provided
            print(json.dumps({"decision": "ask", "reason": "AAPA hook received empty input."}))
            return

        payload = json.loads(raw_input)
        settings = load_settings()

        # 1. Try forwarding to running desktop application
        result = evaluate_via_ipc(payload, host=settings.listen_host, port=settings.listen_port)

        # 2. If desktop UI is not running, evaluate locally with deterministic safety engine
        if not result:
            result = evaluate_standalone(payload)

        # Print single valid JSON response to stdout
        print(json.dumps(result, ensure_ascii=False))

    except Exception as exc:
        # Safe fallback: never crash or hang the agent; prompt the user directly in Antigravity
        fallback = {
            "decision": "ask",
            "reason": f"AAPA evaluation fallback due to error: {exc}"
        }
        print(json.dumps(fallback, ensure_ascii=False))


if __name__ == "__main__":
    main()
