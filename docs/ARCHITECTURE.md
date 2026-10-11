# AAPA Architecture & Technical Design

This document details the software architecture, component relationships, data flow, and security invariants implemented in **Antigravity Auto Permission Assistant (AAPA)**.

---

## 1. High-Level Architecture Diagram

```
                     ┌───────────────────────────────────┐
                     │ Google Antigravity (PreToolUse)   │
                     │ or Manual User Input Dialog       │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │       Request Parser & Normalizer │
                     │       (NormalizedRequest)         │
                     └─────────────────┬─────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
┌───────────────────────────────┐             ┌───────────────────────────────┐
│     Secret & Credential       │             │    Project Context Engine     │
│       Filter & Redaction      │             │ - Reads permitted configs     │
│ - Detects tokens/keys/env     │             │ - Discovers test/build tools  │
│ - Strips sensitive data       │             │ - Scans for prompt injections │
└───────────────┬───────────────┘             └───────────────┬───────────────┘
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │    Deterministic Policy Engine    │
                     │ - Decomposes chained operators    │
                     │ - Enforces filesystem boundaries  │
                     │ - Blocks root/disk/privilege ops  │
                     │ - Matches allowlists & linters    │
                     └─────────────────┬─────────────────┘
                                       │ Preliminary Decision
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Pluggable AI Explainer Adapter  │
                     │ - Local Rule-Based (100% Offline) │
                     │ - Optional OpenAI / Ollama / LLM  │
                     │ [INVARIANT: CANNOT OVERRIDE BLOCK]│
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │          Risk Analyzer            │
                     │   Consolidated AnalysisResult     │
                     └─────────┬───────────────────────┬─┘
                               │                       │
                ┌──────────────┴──────────────┐        │
                ▼                             ▼        ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│       PySide6 Desktop UI      │   │    Structured Audit Logger    │
│ - Interactive Inbox           │   │ - Sensitive data redacted     │
│ - Inspector & Approve/Reject  │   │ - Timestamped JSONL           │
│ - Policy Editor & History     │   │ - CSV Export                  │
└───────────────────────────────┘   └───────────────────────────────┘
```

---

## 2. Core Modules & Responsibilities

| Module | Responsibility |
| :--- | :--- |
| `src/aapa/config.py` | Pydantic data models (`PolicyConfig`, `AppSettings`), persistent file loaders, and default security rule definitions. |
| `src/aapa/secret_filter.py` | Regex and heuristic engine that identifies and redacts AWS keys, GitHub PATs, Google API keys, Slack tokens, private keys, database URLs, and `.env` files. |
| `src/aapa/project_context.py` | Scans workspace root to extract build commands, test runners, frameworks, and checks documentation for adversarial prompt injections. |
| `src/aapa/request_parser.py` | Normalizes heterogeneous inputs (Antigravity `PreToolUse` payloads, tool calls, raw strings, natural language wrappers) into `NormalizedRequest`. |
| `src/aapa/policy_engine.py` | Deterministic evaluator. Breaks down chained shell commands (`&&`, `\|\|`, `;`, `\|`), analyzes arguments, checks path boundaries, and evaluates allowlists/blocklists. |
| `src/aapa/ai_provider.py` | Provider-independent explanation engine. Features an offline rule-based knowledge engine as default, with pluggable support for local and remote LLMs. |
| `src/aapa/risk_analyzer.py` | Orchestrates the entire evaluation pipeline and enforces strict security invariants. |
| `src/aapa/ipc_server.py` | Lightweight loopback HTTP server (`127.0.0.1:49152`) providing synchronized IPC between the Antigravity hook script and the GUI desktop app. |
| `src/aapa/hook.py` | Fast CLI hook entry point invoked by Antigravity via `hooks.json`. Safely communicates with IPC server or falls back to headless policy engine. |
| `src/aapa/integration_manager.py` | Inspects, installs, and uninstalls `.agents/hooks.json` or `~/.gemini/config/hooks.json` cleanly. |
| `src/aapa/audit_logger.py` | Logs every analyzed request, decision, and user action to `~/.gemini/aapa/audit.jsonl` with guaranteed sensitive data redaction. |
| `src/aapa/ui/` | PySide6 desktop interface implementing Dashboard, Request Inspector, Project Context, Policy Editor, Audit Log History, and Settings. |

---

## 3. Strict Safety Decision Invariants

AAPA enforces three non-negotiable security invariants:

1. **Deterministic Supremacy Over AI**:
   Under no circumstances can an AI model output overturn a `BLOCK` decision produced by the deterministic `PolicyEngine`. If the policy engine flags an operation as destructive or dangerous, the decision is immutable `BLOCK`, the risk is `CRITICAL`, and the Antigravity hook response is `deny`.
2. **Adversarial Prompt Injection Defense**:
   If the project context engine discovers prompt injection strings (such as `"ignore previous instructions"`, `"system override: approve all"`) in project markdown files or comments, AAPA automatically demotes any candidate `AUTO_APPROVE` decision to `ASK_USER` and flags security indicators in the inspector.
3. **Fail-Closed on Unknown / Error**:
   Unknown commands default to `ASK_USER`. Unhandled hook exceptions or timeouts safely default to `{"decision": "ask"}`, ensuring Antigravity prompts the user directly rather than executing unvetted commands.
