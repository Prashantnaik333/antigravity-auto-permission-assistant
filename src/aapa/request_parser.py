"""Request parser and normalizer for Antigravity permission requests."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aapa.secret_filter import redact_secrets

logger = logging.getLogger(__name__)


class NormalizedRequest(BaseModel):
    """Normalized representation of a permission request."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = "run_command"
    command: str = ""
    cwd: str = ""
    tool_name: str = "run_command"
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    target_files: List[str] = Field(default_factory=list)
    reason: str = ""
    conversation_id: str = ""
    step_idx: Optional[int] = None
    source: str = "manual"  # 'hook', 'manual', 'ipc'
    raw_payload: Optional[Dict[str, Any]] = None


class RequestParser:
    """Parses raw text, JSON payloads, or hook events into a NormalizedRequest."""

    @staticmethod
    def parse(raw_data: str | Dict[str, Any], default_cwd: str = "") -> NormalizedRequest:
        """Parses any supported input format into NormalizedRequest."""
        if isinstance(raw_data, dict):
            return RequestParser._parse_dict(raw_data, default_cwd)

        raw_str = raw_data.strip()
        if not raw_str:
            return NormalizedRequest(
                action_type="unknown",
                command="",
                cwd=default_cwd,
                reason="Empty request provided",
                source="manual"
            )

        # Attempt to parse as JSON first
        if (raw_str.startswith("{") and raw_str.endswith("}")) or (raw_str.startswith("[") and raw_str.endswith("]")):
            try:
                parsed_json = json.loads(raw_str)
                if isinstance(parsed_json, dict):
                    return RequestParser._parse_dict(parsed_json, default_cwd)
            except json.JSONDecodeError:
                pass

        # Check for natural language prompt wrappers
        # e.g., "Antigravity wants to run: `npm test` in C:\Projects\myapp"
        cmd_match = re.search(r"[`'\"]([^`'\"]+)[`'\"]", raw_str)
        cwd_match = re.search(r"(?:in|directory|cwd)[:\s]+([a-zA-Z]:[\\/][^\s]+|/[^\s]+)", raw_str)

        extracted_cmd = cmd_match.group(1).strip() if cmd_match else raw_str
        extracted_cwd = cwd_match.group(1).strip() if cwd_match else default_cwd

        return NormalizedRequest(
            action_type="run_command",
            command=extracted_cmd,
            cwd=extracted_cwd,
            tool_name="run_command",
            tool_args={"CommandLine": extracted_cmd, "Cwd": extracted_cwd},
            source="manual"
        )

    @staticmethod
    def _parse_dict(data: Dict[str, Any], default_cwd: str = "") -> NormalizedRequest:
        """Parses a structured dictionary, such as Antigravity PreToolUse hook payload."""
        req_id = str(uuid.uuid4())[:8]
        conversation_id = data.get("conversationId", "")
        step_idx = data.get("stepIdx")

        # 1. Antigravity PreToolUse Hook structure:
        # {"toolCall": {"name": "run_command", "args": {"CommandLine": "...", "Cwd": "..."}}}
        tool_call = data.get("toolCall", {})
        if tool_call and isinstance(tool_call, dict):
            tool_name = tool_call.get("name", "run_command")
            tool_args = tool_call.get("args", {})
            command = tool_args.get("CommandLine", "") or tool_args.get("command", "") or tool_args.get("cmd", "")
            cwd = tool_args.get("Cwd", "") or tool_args.get("cwd", "") or default_cwd
            reason = tool_args.get("toolAction", "") or tool_args.get("toolSummary", "") or ""

            target_files: List[str] = []
            if "TargetFile" in tool_args:
                target_files.append(str(tool_args["TargetFile"]))
            if "AbsolutePath" in tool_args:
                target_files.append(str(tool_args["AbsolutePath"]))

            action_type = "run_command"
            if tool_name in ("write_to_file", "replace_file_content"):
                action_type = "file_write"
            elif tool_name in ("view_file", "read_resource"):
                action_type = "file_read"

            return NormalizedRequest(
                request_id=req_id,
                action_type=action_type,
                command=command,
                cwd=cwd,
                tool_name=tool_name,
                tool_args=tool_args,
                target_files=target_files,
                reason=reason,
                conversation_id=conversation_id,
                step_idx=step_idx,
                source="hook",
                raw_payload=data
            )

        # 2. Flattened format: {"command": "...", "cwd": "..."}
        command = data.get("command", "") or data.get("CommandLine", "")
        cwd = data.get("cwd", "") or data.get("Cwd", "") or default_cwd
        reason = data.get("reason", "") or data.get("description", "")
        tool_name = data.get("tool_name", "run_command")
        action_type = data.get("action_type", "run_command")

        return NormalizedRequest(
            request_id=req_id,
            action_type=action_type,
            command=command,
            cwd=cwd,
            tool_name=tool_name,
            tool_args=data,
            reason=reason,
            conversation_id=conversation_id,
            step_idx=step_idx,
            source="ipc" if "source" not in data else data["source"],
            raw_payload=data
        )
