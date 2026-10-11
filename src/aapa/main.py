"""Main command-line and desktop entrypoint for AAPA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aapa import __version__
from aapa.app import launch_gui
from aapa.config import load_policy
from aapa.integration_manager import IntegrationManager
from aapa.project_context import ProjectContextEngine
from aapa.request_parser import RequestParser
from aapa.risk_analyzer import RiskAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aapa",
        description="Antigravity Auto Permission Assistant (AAPA) - Safe AI Permission Management"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--project", "-p", type=str, default="", help="Path to project directory")
    parser.add_argument("--analyze", "-a", type=str, default="", help="Analyze command or JSON payload in headless CLI mode")
    parser.add_argument("--cwd", type=str, default="", help="Working directory for analysis")
    parser.add_argument("--install-hook", action="store_true", help="Install workspace hook into current project (.agents/hooks.json)")
    parser.add_argument("--install-global-hook", action="store_true", help="Install global hook into ~/.gemini/config/hooks.json")
    parser.add_argument("--uninstall-hooks", action="store_true", help="Uninstall AAPA hooks from workspace and global configuration")
    parser.add_argument("--status", action="store_true", help="Display current Antigravity integration status")
    parser.add_argument("--json", action="store_true", help="Output analysis in JSON format")

    args = parser.parse_args()

    # 1. Status Command
    if args.status:
        proj_dir = args.project or Path.cwd()
        status = IntegrationManager.get_status(proj_dir)
        print("=== Antigravity Integration Status ===")
        print(f"Antigravity Platform Detected: {status.antigravity_detected}")
        print(f"Active Mode:                  {status.active_mode}")
        print(f"Workspace Hook Installed:     {status.workspace_hook_installed}")
        print(f"Global Hook Installed:        {status.global_hook_installed}")
        print(f"Hook Invocation Command:      {status.hook_command}")
        print(f"Description:                  {status.description}")
        return

    # 2. Hook Management Commands
    if args.install_hook:
        proj_dir = args.project or Path.cwd()
        ok, msg = IntegrationManager.install_workspace_hook(proj_dir)
        print(msg)
        return

    if args.install_global_hook:
        ok, msg = IntegrationManager.install_global_hook()
        print(msg)
        return

    if args.uninstall_hooks:
        proj_dir = args.project or Path.cwd()
        IntegrationManager.uninstall_workspace_hook(proj_dir)
        IntegrationManager.uninstall_global_hook()
        print("AAPA hooks removed from workspace and global configs.")
        return

    # 3. CLI Analysis Command
    if args.analyze:
        policy = load_policy()
        analyzer = RiskAnalyzer(policy=policy)
        cwd = args.cwd or args.project or str(Path.cwd())
        req = RequestParser.parse(args.analyze, default_cwd=cwd)

        profile = None
        if args.project:
            profile = ProjectContextEngine().scan_project(args.project)

        analysis = analyzer.analyze(req, profile)

        if args.json:
            print(json.dumps(analysis.model_dump(), indent=2, ensure_ascii=False))
        else:
            print("\n" + "=" * 50)
            print(f"AAPA SAFETY ANALYSIS RESULT")
            print("=" * 50)
            print(f"Command:        {analysis.sanitized_command}")
            print(f"Working Dir:    {analysis.cwd}")
            print(f"Category:       {analysis.action_category.value}")
            print(f"Risk Level:     {analysis.risk_level.value}")
            print(f"Recommendation: {analysis.decision.value}")
            print(f"Rule Triggered: {analysis.relevant_rule}")
            print(f"Explanation:    {analysis.explanation}")
            print(f"Hook Response:  {json.dumps(analysis.to_antigravity_hook_response())}")
            print("=" * 50 + "\n")
        return

    # 4. Default: Launch Desktop GUI
    sys.exit(launch_gui(project_path=args.project))


if __name__ == "__main__":
    main()
