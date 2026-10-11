"""Unit tests for Antigravity request parser and normalizer."""

from aapa.request_parser import RequestParser


def test_parse_antigravity_pre_tool_use_hook():
    payload = {
        "conversationId": "conv-123",
        "stepIdx": 5,
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": "npm test",
                "Cwd": "C:/Projects/myapp"
            }
        }
    }
    req = RequestParser.parse(payload)
    assert req.command == "npm test"
    assert req.cwd == "C:/Projects/myapp"
    assert req.tool_name == "run_command"
    assert req.action_type == "run_command"
    assert req.source == "hook"
    assert req.conversation_id == "conv-123"
    assert req.step_idx == 5


def test_parse_file_write_tool_call():
    payload = {
        "conversationId": "conv-456",
        "toolCall": {
            "name": "write_to_file",
            "args": {
                "TargetFile": "C:/Projects/myapp/src/index.js",
                "CodeContent": "console.log('hello');"
            }
        }
    }
    req = RequestParser.parse(payload)
    assert req.action_type == "file_write"
    assert req.tool_name == "write_to_file"
    assert "C:/Projects/myapp/src/index.js" in req.target_files


def test_parse_raw_command_string():
    raw = "pytest tests/ -k test_safety"
    req = RequestParser.parse(raw, default_cwd="C:/myrepo")
    assert req.command == "pytest tests/ -k test_safety"
    assert req.cwd == "C:/myrepo"
    assert req.source == "manual"


def test_parse_prompt_wrapper_string():
    raw = "Antigravity wants to execute command: `npm install react` in directory C:/Projects/frontend"
    req = RequestParser.parse(raw)
    assert req.command == "npm install react"
    assert "C:/Projects/frontend" in req.cwd


def test_parse_malformed_and_empty():
    empty_req = RequestParser.parse("")
    assert empty_req.command == ""
    assert empty_req.action_type == "unknown"

    malformed_json = RequestParser.parse("{not valid json")
    assert malformed_json.command == "{not valid json"
