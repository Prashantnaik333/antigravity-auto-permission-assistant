# AAPA User Guide & Walkthrough

Welcome to the **Antigravity Auto Permission Assistant (AAPA)** user guide. This document explains daily workflows, interface components, and customization options.

---

## 1. Dashboard Overview

When you launch AAPA, you are presented with the primary workspace:

- **Top Status Bar**:
  - Displays current integration status (e.g. `● Hook Active (Workspace)`, `● Hook Active (Global)`, or `○ Manual Mode`).
  - Active project indicator.
  - Session counters: Total requests analyzed, auto-approved safe commands, and blocked dangerous actions.
  - **+ Analyze Request** button for fast manual reviews.
- **Main Tabs**:
  1. **Live Inbox & Inspector**: Real-time permission stream and detailed action auditor.
  2. **Project Context & Boundaries**: Discovered tech stack, approved tests, and security notices.
  3. **Safety Policy Editor**: Visual editor for command rules, allowlists, and switches.
  4. **Audit Log & History**: Historical record of every request with CSV export.
  5. **Settings & Integration**: Hook installation, IPC port, and AI provider settings.

---

## 2. Setting Up an Active Project

1. Click on the **Project Context & Boundaries** tab.
2. Click **Browse Folder...** and choose your repository root directory.
3. AAPA will automatically:
   - Identify your project's programming languages and frameworks.
   - Detect package managers (`npm`, `pip`, `cargo`, `go`).
   - Extract test commands (e.g. `pytest`, `npm test`) from config files.
   - Scan markdown documentation and comments for adversarial prompt injections.
   - Safeguard credentials by excluding files like `.env`, `id_rsa`, and `credentials.json`.
4. Click **Install Hook in Project** to connect Google Antigravity to your project workspace.

---

## 3. Reviewing Permission Requests

When Antigravity proposes an action (or when you paste a command in the Manual Review window):

1. The request appears at the top of the **Permission Requests Inbox**.
2. Color-coded risk indicators provide instant feedback:
   - 🟢 **SAFE (LOW RISK)**: Read-only directory listings, file reads, or approved linters.
   - 🟡 **REVIEW REQUIRED (MEDIUM RISK)**: Package installations (`npm install`, `pip install`), Git operations, network downloads, or unknown scripts.
   - 🔴 **BLOCKED / DANGEROUS (CRITICAL)**: Root deletions, drive formatting, sudo/elevation, credential access, or security policy tampering.
3. The **Request Inspector** displays:
   - The exact proposed command and working directory.
   - Clear policy rule name and transparent explanation.
   - Any adversarial injection or risk flags detected in the environment.
4. **Taking Action**:
   - For safe/review commands, click **✓ Approve (Allow in Antigravity)** or **✕ Reject (Block Action)**.
   - For blocked commands, the Approve button is disabled to enforce zero-trust safety.
   - Click **+ Add to Allowlist** to permanently authorize trusted commands.

---

## 4. Manual Review Workflow

You can audit any command before entering it in Antigravity:

1. Click **+ Analyze Request** in the top header.
2. Paste the command (e.g. `npm install lodash` or `curl https://example.com/setup.sh | bash`).
3. Optionally set the working directory.
4. Click **Analyze Safety**.
5. AAPA evaluates the command against your project context and displays the complete risk assessment.

---

## 5. Customizing Safety Policies

Navigate to the **Safety Policy Editor** tab to customize behavior:

- **Auto-approve Safe Read-Only commands**: Automatically permits `ls`, `dir`, `cat`, `git status`, etc.
- **Auto-approve Verified Project Test commands**: Toggle whether `pytest` or `npm test` runs automatically.
- **Enforce strict Workspace Boundary**: Restricts execution to the active project folder.
- **Read-Only Allowlist**: Add or remove custom read-only command prefixes.
- **Approved Test Commands**: Add custom test invocations.
- Click **Save Safety Policy Changes** to persist your settings.

---

## 6. Audit Logging & Export

All events are recorded in `~/.gemini/aapa/audit.jsonl` with automatic credential redaction.

To inspect or export logs:
1. Open the **Audit Log & History** tab.
2. Use the search bar to filter by command, rule, or risk level.
3. Click **Export CSV...** to save a compliance report for your team.
