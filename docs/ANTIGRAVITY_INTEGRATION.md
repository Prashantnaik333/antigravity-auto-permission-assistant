# Google Antigravity Integration Specification & Limitations

This document provides the authoritative technical reference for how **Antigravity Auto Permission Assistant (AAPA)** interacts with the Google Antigravity AI platform across the Antigravity CLI (`agy`), Antigravity IDE, and Antigravity 2.0 Desktop.

---

## 1. Integration Capability Investigation

Before designing AAPA, we conducted an exhaustive investigation into Google Antigravity's supported integration mechanisms and documentation.

### Key Architectural Findings:
1. **Documented Lifecycle Hooks Exist**:
   Google Antigravity officially supports external lifecycle hooks configured via `hooks.json` placed either in the project root (`<project-root>/.agents/hooks.json`) or globally in the user configuration directory (`~/.gemini/config/hooks.json`).
2. **`PreToolUse` Hook Protocol**:
   When Antigravity prepares to execute a tool (e.g. `run_command`, `write_to_file`, `replace_file_content`), it fires the `PreToolUse` event synchronously before execution.
   - The handler runs as an external shell command (`type: "command"`).
   - Antigravity transmits full context via standard input (`stdin`) as a JSON object.
   - Antigravity reads the handler's decision from standard output (`stdout`) as a JSON object.
3. **Official Decision Schema**:
   The output JSON object supports the following decision values:
   - `"allow"`: Automatically authorizes and proceeds with tool execution without human prompt.
   - `"deny"`: Hard blocks execution immediately and notifies the model.
   - `"ask"`: Prompts the human user for approval (respects cached permissions).
   - `"force_ask"`: Always prompts the user for approval, ignoring any cached permissions.
4. **No Undocumented UI Injection**:
   Antigravity 2.0 Desktop does **not** expose a remote UI automation API or public WebSocket for simulating mouse clicks on native buttons. AAPA strictly avoids memory tampering, DLL injection, accessibility hacks, or process scraping. All integration relies purely on the official `PreToolUse` protocol and user-controlled workflows.

---

## 2. Integration Modes Implemented in AAPA

AAPA implements a multi-tier integration architecture:

### Mode A: Real-Time Lifecycle Hook with Desktop IPC Bridge (Recommended)
```
┌─────────────────────────────────┐
│     Google Antigravity AI       │
│   (CLI, IDE, or Desktop 2.0)    │
└────────────────┬────────────────┘
                 │ 1. PreToolUse toolCall via stdin
                 ▼
┌─────────────────────────────────┐
│       aapa.hook (CLI Proxy)     │
└────────────────┬────────────────┘
                 │ 2. HTTP POST /api/evaluate
                 ▼
┌─────────────────────────────────┐
│       AAPA Desktop UI (IPC)     │
│   - Policy Engine               │
│   - Project Context Engine      │
│   - Interactive User Inbox      │
└────────────────┬────────────────┘
                 │ 3. JSON decision ("allow" / "deny" / "ask")
                 ▼
┌─────────────────────────────────┐
│       Google Antigravity        │
│   (Executes or Blocks Command)  │
└─────────────────────────────────┘
```

1. Antigravity invokes `python -m aapa.hook` when a tool call is proposed.
2. The hook transmits the request to the running AAPA desktop application via local loopback IPC (`http://127.0.0.1:49152`).
3. If the action is **Low-Risk & Allowlisted**: AAPA automatically returns `{"decision": "allow"}`.
4. If the action is **Dangerous / Blocked**: AAPA immediately returns `{"decision": "deny"}`.
5. If the action is **Medium-Risk (Review Required)**: AAPA rings the desktop inbox, alerts the user, and waits up to 20 seconds for the user to click Approve or Reject.
6. If the user does not respond within 20 seconds, AAPA returns `{"decision": "ask"}`, cleanly falling back to Antigravity's native in-app confirmation dialog.

### Mode B: Standalone Headless Hook (When Desktop GUI is Closed)
If the user is running Antigravity without the AAPA GUI open:
1. `python -m aapa.hook` detects that the local IPC port is offline.
2. It falls back to running AAPA's deterministic `PolicyEngine` directly in-process.
3. Automatically allowlists verified low-risk read-only commands and blocks dangerous actions according to `config/default_policy.json`.

### Mode C: Manual Review & Paste Window
For environments where hooks are disabled or prohibited by team policy:
1. The user copies any command, JSON payload, or Antigravity prompt.
2. The user clicks **+ Analyze Request** in the AAPA Dashboard.
3. AAPA parses the action, scans repository context, evaluates deterministic safety rules, and presents the decision with full explanation.

---

## 3. Hook Configuration Format

When installed via AAPA's **Settings & Integration** tab, the following configuration is merged into `.agents/hooks.json` or `~/.gemini/config/hooks.json`:

```json
{
  "aapa-permission-assistant": {
    "enabled": true,
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          {
            "type": "command",
            "command": "python -m aapa.hook",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

---

## 4. Honest Limitations & Security Guarantees

- **Timeout Boundaries**: Antigravity has a default 30-second hook execution timeout. AAPA limits interactive user waits to 20 seconds to prevent hanging the AI loop.
- **Fail-Safe Fallback**: If an unhandled exception or malformed JSON is received, `aapa.hook` always returns `{"decision": "ask"}`. Antigravity will prompt the user directly rather than failing silently.
- **Zero Security Bypass**: AAPA never attempts to bypass Antigravity's permissions. It acts as an upstream intelligent filter and auditor.
