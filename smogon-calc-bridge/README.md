# Smogon Calc Bridge

This directory contains a Node.js bridge server that allows Python code to use the official [@smogon/calc](https://www.npmjs.com/package/@smogon/calc) damage calculator.

## Why @smogon/calc?

- **100% Accurate**: Official Pokémon Showdown damage calculation
- **Fully Featured**: Supports all abilities (Multiscale, Protosynthesis, etc.), Terastallization, weather, terrain, and more
- **Maintained**: Updated by Smogon team for new generations

## Installation

```bash
npm install
```

This installs `@smogon/calc` v0.10.0.

## Usage

### Standalone Test

```bash
echo '{"attacker":{"name":"Gholdengo","nature":"Modest","evs":{"spa":252},"ivs":{},"item":"Choice Specs","ability":"Good as Gold","level":50},"defender":{"name":"Dragonite","nature":"Jolly","evs":{"atk":252},"ivs":{},"item":null,"ability":"Multiscale","level":50},"move":"Make It Rain","field":{}}' | node calc_server.js
```

### From Python

```python
from predictor.engine.smogon_calc_wrapper import SmogonCalcWrapper

with SmogonCalcWrapper() as calc:
    result = calc.calculate_damage(
        attacker_name="Gholdengo",
        attacker_spread=gholdengo_spread,
        defender_name="Dragonite",
        defender_spread=dragonite_spread,
        move_name="Make It Rain",
        attacker_item="Choice Specs",
        defender_ability="Multiscale"
    )

    print(result.description)
    # Output: "252+ SpA Choice Specs Gholdengo Make It Rain vs. 4 HP / 0 SpD Multiscale Dragonite: 85-101 (50.8 - 60.4%) -- guaranteed 2HKO"
```

## Input Format

```json
{
  "attacker": {
    "name": "Gholdengo",
    "nature": "Modest",
    "evs": { "hp": 4, "spa": 252, "spe": 252 },
    "ivs": {},
    "item": "Choice Specs",
    "ability": "Good as Gold",
    "level": 50,
    "teraType": null
  },
  "defender": {
    "name": "Dragonite",
    "nature": "Jolly",
    "evs": { "hp": 4, "atk": 252, "spe": 252 },
    "ivs": {},
    "item": null,
    "ability": "Multiscale",
    "level": 50,
    "teraType": null
  },
  "move": "Make It Rain",
  "field": {
    "weather": null,
    "terrain": null,
    "isCrit": false,
    "attackerSide": { "isReflect": false, "isLightScreen": false },
    "defenderSide": { "isReflect": false, "isLightScreen": false }
  }
}
```

## Output Format

```json
{
  "success": true,
  "damage": [115, 117, 118, ...],
  "damageRange": [115, 136],
  "description": "252+ SpA Gholdengo Make It Rain vs. 0 HP / 0 SpD Dragonite: 115-136 (69.2 - 81.9%) -- guaranteed 2HKO",
  "kochance": {"chance": 1, "n": 2, "text": "guaranteed 2HKO"},
  "minPercent": 69.27,
  "maxPercent": 81.92,
  "defender": {"maxHP": 166}
}
```

## Architecture

```
Python (predictor/engine/smogon_calc_wrapper.py)
    |
    | subprocess.Popen
    v
Node.js (smogon-calc-bridge/calc_server.js)
    |
    | import
    v
@smogon/calc (official library)
```

Communication: JSON over stdin/stdout

## Performance

- **Latency**: ~10-20ms per calculation (with persistent connection)
- **Throughput**: ~50-100 calculations/second
- **Memory**: ~30-50MB for Node.js process

## Troubleshooting

### "Module not found" error

Make sure you ran `npm install` in this directory.

### Process hangs

The bridge server uses stdin/stdout for communication. Make sure you're sending valid JSON followed by a newline character.

### Calculation errors

Check the `stderr` output for error messages. Common issues:

- Invalid Pokémon name (use exact Showdown names, e.g., "Ninetales-Alola")
- Invalid move name
- Invalid item/ability name

## License

This bridge code is part of the new_watch_game_system project.
@smogon/calc itself is licensed under MIT by the Smogon team.
