from pathlib import Path

from predictor.engine.team_parser import TeamParser


def read_fixture(name: str) -> str:
    base = Path(__file__).parent / "data" / name
    return base.read_text(encoding="utf-8")


def test_pokepaste_to_showdown_with_ev_fill():
    parser = TeamParser()
    team_text = read_fixture("team_a.paste")
    showdown_str = parser.parse_to_showdown(
        team_text,
        {
            "flutter mane": {"hp": 0, "def": 4, "spa": 252, "spe": 252},
        },
    )

    # Provided EVs should be used for Flutter Mane
    assert "Flutter Mane @ Focus Sash" in showdown_str
    assert "EVs: 4 Def / 252 SpA / 252 Spe" in showdown_str

    # Arcanine should fall back to the default 4/252/252 template
    assert "Arcanine @ Safety Goggles" in showdown_str
    assert "EVs: 4 HP / 252 SpA / 252 Spe" in showdown_str


def test_parser_respects_blank_lines():
    parser = TeamParser()
    team_text = read_fixture("team_b.paste")
    showdown_str = parser.parse_to_showdown(team_text)

    # Ensure each Pokémon becomes its own block
    assert showdown_str.count("Iron Bundle @ Booster Energy") == 1
    assert showdown_str.count("Amoonguss @ Sitrus Berry") == 1


def test_parser_extracts_species_from_nickname():
    parser = TeamParser()
    pokepaste = """Specter (Flutter Mane) @ Focus Sash
Ability: Protosynthesis
Tera Type: Fairy
- Moonblast
"""
    entries = parser.parse_entries(pokepaste)
    assert entries[0].name == "Specter"
    assert entries[0].species == "Flutter Mane"
