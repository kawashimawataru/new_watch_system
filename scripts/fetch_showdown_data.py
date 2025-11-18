#!/usr/bin/env python3
"""Download Pokémon Showdown data files and convert them to JSON."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "showdown"
SOURCES = {
    "pokedex.js": "https://play.pokemonshowdown.com/data/pokedex.js",
    "moves.js": "https://play.pokemonshowdown.com/data/moves.js",
    "items.js": "https://play.pokemonshowdown.com/data/items.js",
    "typechart.js": "https://play.pokemonshowdown.com/data/typechart.js",
}


def download() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in SOURCES.items():
        target = DATA_DIR / filename
        print(f"Downloading {url} -> {target}")
        subprocess.check_call(["curl", "-sSfL", url, "-o", str(target)])


def convert(js_file: Path, export_key: str) -> Dict:
    script = (
        "const fs=require('fs');"
        f"const data=require('{js_file.as_posix()}');"
        f"const payload=data.{export_key} || data;"
        "process.stdout.write(JSON.stringify(payload));"
    )
    output = subprocess.check_output(["node", "-e", script])
    return json.loads(output)


def main() -> None:
    download()
    datasets = [
        ("pokedex.js", "BattlePokedex", "pokedex.json"),
        ("moves.js", "BattleMovedex", "moves.json"),
        ("items.js", "BattleItems", "items.json"),
        ("typechart.js", "BattleTypeChart", "typechart.json"),
    ]
    for src, key, dest in datasets:
        js_path = DATA_DIR / src
        target = DATA_DIR / dest
        print(f"Converting {js_path} -> {target}")
        data = convert(js_path, key)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(data, handle)


if __name__ == "__main__":
    main()
