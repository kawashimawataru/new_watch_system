#!/usr/bin/env python3
"""
Explainable AI Agent Runner

This script launches the AI agent that provides detailed explanations for its moves.
It connects to a local Pokemon Showdown server.

Usage:
    python scripts/run_explainable_agent.py
"""

import os
import sys
import subprocess
import time

def main():
    # Project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add project root to PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    
    print("🚀 Launching Explainable AI Agent...")
    print(f"📂 Project Root: {project_root}")
    
    # Check if Showdown is likely running (simple check)
    # This is just a reminder, not a strict check
    print("\n⚠️  Ensure Pokemon Showdown is running on localhost:8000")
    print("   (cd pokemon-showdown && node pokemon-showdown start)\n")
    
    try:
        # Run the player module
        subprocess.run(
            [sys.executable, "-m", "frontend.battle_ai_player"],
            cwd=project_root,
            env=env,
            check=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Agent stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Agent crashed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
