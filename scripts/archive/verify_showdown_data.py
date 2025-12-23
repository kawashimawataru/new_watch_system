#!/usr/bin/env python3
"""Compare local Showdown datasets with the upstream official files."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "showdown"
SOURCES = {
    "pokedex.js": "https://play.pokemonshowdown.com/data/pokedex.js",
    "moves.js": "https://play.pokemonshowdown.com/data/moves.js",
    "items.js": "https://play.pokemonshowdown.com/data/items.js",
    "typechart.js": "https://play.pokemonshowdown.com/data/typechart.js",
}
DATASETS = [
    ("pokedex.js", "BattlePokedex", "pokedex.json"),
    ("moves.js", "BattleMovedex", "moves.json"),
    ("items.js", "BattleItems", "items.json"),
    ("typechart.js", "BattleTypeChart", "typechart.json"),
]


def convert(js_file: Path, export_key: str) -> Dict:
    script = (
        "const fs=require('fs');"
        f"const data=require('{js_file.as_posix()}');"
        f"const payload=data.{export_key} || data;"
        "process.stdout.write(JSON.stringify(payload));"
    )
    output = subprocess.check_output(["node", "-e", script])
    return json.loads(output)


def fetch_remote(filename: str, url: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp())
    target = tmp_dir / filename
    subprocess.check_call(["curl", "-sSfL", url, "-o", str(target)])
    return target


def main() -> None:
    mismatches = []
    for source, key, dest in DATASETS:
        local_path = DATA_DIR / dest
        if not local_path.exists():
            mismatches.append(dest)
            continue
        remote_js = fetch_remote(source, SOURCES[source])
        remote_payload = convert(remote_js, key)
        local_payload = json.loads(local_path.read_text(encoding="utf-8"))
        if remote_payload != local_payload:
            mismatches.append(dest)

    if mismatches:
        print("The following datasets are outdated:", ", ".join(mismatches))
        print("Run `python scripts/fetch_showdown_data.py` and rerun this verifier.")
        sys.exit(1)
    print("✅ Local Showdown datasets match the upstream sources.")


if __name__ == "__main__":
    main()
