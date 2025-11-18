"""
Simple CLI front-end for feeding data into evaluate_position.

Usage:
    python -m frontend.input_cli --team-a path/to/a.paste --team-b path/to/b.paste \
        --battle-log path/to/log.json --evs path/to/evs.json

If paths are omitted the script falls back to interactive prompts that accept
multi-line input terminated by a line containing only a single period (.).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from predictor.core.position_evaluator import evaluate_position


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local front-end for the VGC predictor.")
    parser.add_argument("--team-a", type=Path, help="Path to team A Pokepaste text.")
    parser.add_argument("--team-b", type=Path, help="Path to team B Pokepaste text.")
    parser.add_argument("--battle-log", type=Path, help="Path to battle log JSON.")
    parser.add_argument("--evs", type=Path, help="Path to estimated EV JSON.")
    parser.add_argument(
        "--algorithm",
        choices=["heuristic", "mcts", "ml"],
        default="heuristic",
        help="Evaluation algorithm to use.",
    )
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Load sample fixtures from tests/data for a quick smoke test.",
    )
    return parser.parse_args()


def load_sample_payloads() -> tuple[str, str, Dict[str, Any], Dict[str, Dict[str, Dict[str, int]]]]:
    base = Path(__file__).resolve().parent.parent / "tests" / "data"
    team_a = (base / "team_a.paste").read_text(encoding="utf-8")
    team_b = (base / "team_b.paste").read_text(encoding="utf-8")
    battle_log = json.loads((base / "sample_battle_log.json").read_text(encoding="utf-8"))
    evs = {
        "A": {
            "Flutter Mane": {"hp": 0, "def": 4, "spa": 252, "spe": 252},
            "Arcanine": {"hp": 252, "atk": 252, "spe": 4},
        },
        "B": {
            "Iron Bundle": {"hp": 0, "def": 4, "spa": 252, "spe": 252},
            "Amoonguss": {"hp": 252, "def": 124, "spd": 132},
        },
    }
    return team_a, team_b, battle_log, evs


def read_text_input(path: Optional[Path], label: str) -> str:
    if path:
        return path.read_text(encoding="utf-8")
    print(f"Paste {label} below. Finish with a single '.' on its own line.")
    print("-" * 60)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".":
            break
        lines.append(line)
    text = "\n".join(lines).strip()
    if not text:
        raise ValueError(f"{label} cannot be empty.")
    return text


def read_json_input(path: Optional[Path], label: str) -> Dict[str, Any]:
    raw = read_text_input(path, label)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for {label}: {exc}") from exc


def main():
    args = parse_args()

    if args.sample_data:
        team_a, team_b, battle_log, evs = load_sample_payloads()
    else:
        team_a = read_text_input(args.team_a, "Team A Pokepaste")
        team_b = read_text_input(args.team_b, "Team B Pokepaste")
        battle_log = read_json_input(args.battle_log, "Battle log JSON")
        evs = read_json_input(args.evs, "Estimated EV JSON")

    result = evaluate_position(
        team_a,
        team_b,
        battle_log,
        evs,
        algorithm=args.algorithm,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
