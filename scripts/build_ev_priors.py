#!/usr/bin/env python3
"""
Convert ladder usage spreadsheets into ev_priors.json.

Input CSV format:
name,label,nature,weight,hp,atk,def,spa,spd,spe
Flutter Mane,timid_focus_sash,Timid,0.7,0,0,4,252,0,252
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build EV priors from usage stats CSV.")
    parser.add_argument("--input", "-i", type=Path, required=True, help="CSV file with spread usage.")
    parser.add_argument("--output", "-o", type=Path, default=Path("data/ev_priors.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entries: Dict[str, List[dict]] = defaultdict(list)
    with args.input.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = row["name"]
            label = row.get("label") or "spread"
            nature = row.get("nature") or "Serious"
            weight = float(row.get("weight") or 1.0)
            evs = {stat: int(row.get(stat, 0) or 0) for stat in ["hp", "atk", "def", "spa", "spd", "spe"]}
            entries[name].append(
                {
                    "label": label,
                    "nature": nature,
                    "weight": weight,
                    "evs": evs,
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2)


if __name__ == "__main__":
    main()
