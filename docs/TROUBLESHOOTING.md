# AAPA Troubleshooting & Diagnostics

This guide addresses common questions, troubleshooting steps, and error resolutions when running **Antigravity Auto Permission Assistant (AAPA)**.

---

## 1. Antigravity Hook Is Not Intercepting Commands

### Symptoms:
Antigravity executes commands or shows default permission dialogs without sending them to AAPA.

### Resolutions:
1. **Verify Hook Status**:
   Run the diagnostics command in your terminal:
   ```cmd
   python -m aapa.main --status
   ```
   Ensure `Workspace Hook Installed` or `Global Hook Installed` is `True`.
2. **Check `.agents/hooks.json` Path**:
   Verify that `.agents/hooks.json` exists in your project root and contains the `"aapa-permission-assistant"` entry.
3. **Verify Python In PATH**:
   If Antigravity cannot find `python`, open `.agents/hooks.json` and replace `"python -m aapa.hook"` with the absolute path to your Python virtual environment executable:
   `"C:\\Path\\To\\Repo\\.venv\\Scripts\\python.exe -m aapa.hook"`
4. **Reinstall Hook**:
   In the AAPA UI under **Settings & Integration**, click **Uninstall Hooks** and then **Install Hook in Project**.

---

## 2. Port Conflict (Address Already in Use: 49152)

### Symptoms:
Log reports: `Could not start AAPA IPC server on 49152: [Errno 10048] Only one usage of each socket address is normally permitted.`

### Resolutions:
1. Another instance of AAPA may already be running in the background. Check Windows Task Manager or run:
   ```powershell
   Get-Process python* | Stop-Process -Force
   ```
2. Or change the port: In **Settings & Integration**, change the port from `49152` to an available port (e.g. `49180`) and click **Save Settings**.

---

## 3. PySide6 / Qt Display Issues on Headless Windows or Remote Sessions

### Symptoms:
`qt.qpa.plugin: Could not find the Qt platform plugin "windows"` or UI fails to render over SSH/RDP.

### Resolutions:
1. Run in Headless CLI Mode:
   AAPA functions completely in headless CLI mode without requiring PySide6 rendering:
   ```cmd
   python -m aapa.main --analyze "npm test" --cwd "C:/Projects/myapp"
   ```
2. Reinstall PySide6 wheels:
   ```cmd
   pip install --force-reinstall PySide6
   ```

---

## 4. Resetting Policies After Accidental Misconfiguration

### Symptoms:
Commands that should be allowlisted are blocked, or rules were accidentally deleted.

### Resolutions:
1. Open the **Safety Policy Editor** tab in the AAPA Dashboard.
2. Click **Reset to Default Safety Policy** and confirm.
3. Or manually delete `%LOCALAPPDATA%\aapa\policy.json`, and AAPA will automatically restore the official default policy on next launch.

---

## 5. Diagnostic Self-Test

To verify that your local AAPA engine, policy rules, and context scanners are healthy:

```cmd
pytest tests/ -v
```
All 35 tests should pass.
