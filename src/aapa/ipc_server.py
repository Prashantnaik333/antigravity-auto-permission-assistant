"""Local IPC server connecting Antigravity hook invocations to the AAPA desktop UI."""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from aapa.config import Decision
from aapa.request_parser import NormalizedRequest, RequestParser
from aapa.risk_analyzer import AnalysisResult, RiskAnalyzer

logger = logging.getLogger(__name__)


class PendingRequestSlot:
    """Synchronization slot for user interactive decisions."""

    def __init__(self, request: NormalizedRequest, analysis: AnalysisResult):
        self.request = request
        self.analysis = analysis
        self.event = threading.Event()
        self.user_decision: Optional[str] = None  # 'allow' or 'deny'
        self.user_reason: Optional[str] = None


class AAPAIPCRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for local loopback IPC."""

    server: AAPAIPCServer  # Type hint for parent server reference

    def do_GET(self) -> None:
        """Health check and status queries."""
        if self.path == "/api/health":
            self._send_json(200, {
                "status": "online",
                "app": "Antigravity Auto Permission Assistant",
                "version": "1.0.0"
            })
        elif self.path == "/api/pending":
            pending_list = [
                slot.analysis.model_dump()
                for slot in self.server.pending_requests.values()
            ]
            self._send_json(200, {"pending": pending_list})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Processes hook evaluations or UI user actions."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception as exc:
            self._send_json(400, {"error": f"Invalid JSON payload: {exc}"})
            return

        if self.path == "/api/evaluate":
            self._handle_evaluate(body)
        elif self.path == "/api/decision":
            self._handle_user_decision(body)
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_evaluate(self, raw_payload: Dict[str, Any]) -> None:
        """Analyzes a hook request and waits for user confirmation if required."""
        normalized = RequestParser.parse(raw_payload)
        analysis = self.server.analyzer.analyze(normalized, self.server.current_project_profile)

        # Notify UI of new request
        if self.server.on_request_received:
            self.server.on_request_received(normalized, analysis)

        # 1. AUTO_APPROVE: Immediate allow
        if analysis.decision == Decision.AUTO_APPROVE:
            self._send_json(200, analysis.to_antigravity_hook_response())
            return

        # 2. BLOCK: Immediate deny
        if analysis.decision == Decision.BLOCK:
            self._send_json(200, analysis.to_antigravity_hook_response())
            return

        # 3. ASK_USER: Register pending slot and wait for UI interaction or timeout
        slot = PendingRequestSlot(normalized, analysis)
        self.server.pending_requests[normalized.request_id] = slot

        # Wait with timeout (e.g., 20 seconds, before Antigravity's default 30s hook timeout)
        got_response = slot.event.wait(timeout=20.0)
        self.server.pending_requests.pop(normalized.request_id, None)

        if got_response and slot.user_decision:
            resp = {
                "decision": slot.user_decision,
                "reason": slot.user_reason or f"User {slot.user_decision}ed via AAPA Dashboard."
            }
        else:
            # On timeout, safely fallback to 'ask' so Antigravity asks the user directly
            resp = {
                "decision": "ask",
                "reason": "AAPA review timeout; deferring decision to Antigravity interface."
            }

        self._send_json(200, resp)

    def _handle_user_decision(self, body: Dict[str, Any]) -> None:
        """Receives user approval or rejection from the AAPA desktop UI."""
        req_id = body.get("request_id", "")
        decision = body.get("decision", "ask")  # 'allow' or 'deny'
        reason = body.get("reason", "")

        slot = self.server.pending_requests.get(req_id)
        if slot:
            slot.user_decision = decision
            slot.user_reason = reason
            slot.event.set()
            self._send_json(200, {"status": "ok", "message": f"Applied {decision} to {req_id}"})
        else:
            self._send_json(404, {"error": "Pending request not found or expired"})

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        """Sends JSON response."""
        resp_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard HTTP server stdout noise."""
        return


class AAPAIPCServer(HTTPServer):
    """Custom HTTP Server holding pending request slots and analyzer state."""

    def __init__(
        self,
        server_address: tuple[str, int],
        analyzer: RiskAnalyzer,
        on_request_received: Optional[Callable[[NormalizedRequest, AnalysisResult], None]] = None
    ):
        super().__init__(server_address, AAPAIPCRequestHandler)
        self.analyzer = analyzer
        self.on_request_received = on_request_received
        self.pending_requests: Dict[str, PendingRequestSlot] = {}
        self.current_project_profile = None
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def start_background(self) -> None:
        """Starts server in a background daemon thread."""
        self.is_running = True
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        logger.info("AAPA IPC Server running at http://%s:%d", self.server_address[0], self.server_address[1])

    def stop(self) -> None:
        """Gracefully shuts down server."""
        if self.is_running:
            self.shutdown()
            self.server_close()
            self.is_running = False
            logger.info("AAPA IPC Server stopped.")
