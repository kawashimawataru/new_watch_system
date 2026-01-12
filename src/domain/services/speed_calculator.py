"""
Speed Calculator - LLM用素早さ順序計算

既存のTurnOrderServiceをラップし、LLMが理解しやすい形式で出力する。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SpeedEntry:
    """個別のポケモンの素早さ情報"""
    name: str
    species: str
    effective_speed: int
    is_player: bool
    raw_speed: Optional[int] = None
    modifiers: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "species": self.species,
            "effective_speed": self.effective_speed,
            "is_player": self.is_player,
            "modifiers": self.modifiers,
        }


@dataclass
class SpeedOrder:
    """素早さ順序情報"""
    order: List[SpeedEntry] = field(default_factory=list)
    is_trick_room: bool = False
    has_tailwind_player: bool = False
    has_tailwind_opponent: bool = False
    weather: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order": [e.to_dict() for e in self.order],
            "is_trick_room": self.is_trick_room,
            "has_tailwind_player": self.has_tailwind_player,
            "has_tailwind_opponent": self.has_tailwind_opponent,
            "weather": self.weather,
        }
    
    def to_summary_text(self) -> str:
        """LLM用のサマリーテキスト"""
        lines = []
        
        # フィールド状態
        if self.is_trick_room:
            lines.append("🌀 トリックルーム発動中（遅い順に行動）")
        if self.has_tailwind_player:
            lines.append("💨 自分側に追い風（素早さ2倍）")
        if self.has_tailwind_opponent:
            lines.append("💨 相手側に追い風（素早さ2倍）")
        if self.weather:
            lines.append(f"🌤️ 天候: {self.weather}")
        
        # 行動順
        lines.append("【行動順序】")
        for i, entry in enumerate(self.order, 1):
            side = "自分" if entry.is_player else "相手"
            modifiers_str = f" ({', '.join(entry.modifiers)})" if entry.modifiers else ""
            lines.append(f"  {i}. {entry.species} [{side}] - 実効S: {entry.effective_speed}{modifiers_str}")
        
        return "\n".join(lines)
    
    def get_first_mover(self) -> Optional[SpeedEntry]:
        """最速のポケモンを返す"""
        return self.order[0] if self.order else None
    
    def player_moves_first(self) -> bool:
        """自分の方が先に動けるか"""
        first = self.get_first_mover()
        return first.is_player if first else False


class SpeedCalculator:
    """
    LLM用の素早さ順序計算サービス
    """
    
    # 特性による素早さ補正
    SPEED_ABILITIES: Dict[str, str] = {
        "swiftswim": "すいすい(雨)",
        "chlorophyll": "ようりょくそ(晴)",
        "sandrush": "すなかき(砂)",
        "slushrush": "ゆきかき(雪)",
        "quarkdrive": "クォークチャージ",
        "protosynthesis": "古代活性",
        "unburden": "かるわざ",
        "surgesurfer": "サーフテール",
    }
    
    # アイテムによる素早さ補正
    SPEED_ITEMS: Dict[str, str] = {
        "choicescarf": "こだわりスカーフ(1.5倍)",
        "ironball": "くろいてっきゅう(0.5倍)",
    }
    
    @classmethod
    def calculate_from_battle(cls, battle) -> SpeedOrder:
        """
        poke-env DoubleBattleから素早さ順序を計算
        """
        from src.domain.services.turn_order_service import get_turn_order_service
        
        service = get_turn_order_service()
        raw_order = service.get_predicted_turn_order(battle)
        
        # SpeedOrderに変換
        speed_order = SpeedOrder()
        
        # フィールド状態
        speed_order.is_trick_room = "trickroom" in battle.fields
        speed_order.has_tailwind_player = "tailwind" in battle.side_conditions
        speed_order.has_tailwind_opponent = "tailwind" in battle.opponent_side_conditions
        
        if battle.weather:
            weather_name = list(battle.weather.keys())[0] if battle.weather else None
            speed_order.weather = weather_name
        
        for name, eff_speed, is_player in raw_order:
            entry = SpeedEntry(
                name=name,
                species=name,
                effective_speed=int(eff_speed),
                is_player=is_player,
                modifiers=[]
            )
            speed_order.order.append(entry)
        
        return speed_order
    
    @classmethod
    def calculate_from_state(
        cls,
        player_pokemon: List[Dict[str, Any]],
        opponent_pokemon: List[Dict[str, Any]],
        field_state: Dict[str, Any] = None,
    ) -> SpeedOrder:
        """
        BattleState形式のデータから素早さ順序を計算
        
        Args:
            player_pokemon: 自分のポケモンリスト (name, speed, item, ability, etc.)
            opponent_pokemon: 相手のポケモンリスト
            field_state: フィールド状態 (trick_room, tailwind, weather)
        """
        field_state = field_state or {}
        speed_order = SpeedOrder()
        
        # フィールド状態
        speed_order.is_trick_room = field_state.get("trick_room", False)
        speed_order.has_tailwind_player = field_state.get("tailwind_player", False)
        speed_order.has_tailwind_opponent = field_state.get("tailwind_opponent", False)
        speed_order.weather = field_state.get("weather")
        
        entries: List[SpeedEntry] = []
        
        # 自分のポケモン
        for poke in player_pokemon:
            entry = cls._calculate_entry(poke, is_player=True, field_state=field_state)
            entries.append(entry)
        
        # 相手のポケモン
        for poke in opponent_pokemon:
            entry = cls._calculate_entry(poke, is_player=False, field_state=field_state)
            entries.append(entry)
        
        # ソート（トリックルームなら遅い順、通常は速い順）
        entries.sort(
            key=lambda e: e.effective_speed,
            reverse=not speed_order.is_trick_room
        )
        
        speed_order.order = entries
        return speed_order
    
    @classmethod
    def _calculate_entry(
        cls,
        pokemon: Dict[str, Any],
        is_player: bool,
        field_state: Dict[str, Any],
    ) -> SpeedEntry:
        """個別ポケモンの実効素早さを計算"""
        name = pokemon.get("name", "Unknown")
        base_speed = pokemon.get("speed", 100)  # デフォルト100
        
        effective_speed = base_speed
        modifiers = []
        
        # アイテム補正
        item = pokemon.get("item", "").lower()
        if item == "choicescarf":
            effective_speed = int(effective_speed * 1.5)
            modifiers.append("スカーフ")
        elif item == "ironball":
            effective_speed = int(effective_speed * 0.5)
            modifiers.append("くろいてっきゅう")
        
        # 特性補正
        ability = pokemon.get("ability", "").lower()
        weather = field_state.get("weather", "").lower()
        
        if ability == "swiftswim" and "rain" in weather:
            effective_speed *= 2
            modifiers.append("すいすい")
        elif ability == "chlorophyll" and "sun" in weather:
            effective_speed *= 2
            modifiers.append("ようりょくそ")
        elif ability == "sandrush" and "sand" in weather:
            effective_speed *= 2
            modifiers.append("すなかき")
        elif ability == "slushrush" and ("snow" in weather or "hail" in weather):
            effective_speed *= 2
            modifiers.append("ゆきかき")
        
        # 追い風
        if is_player and field_state.get("tailwind_player"):
            effective_speed *= 2
            modifiers.append("追い風")
        elif not is_player and field_state.get("tailwind_opponent"):
            effective_speed *= 2
            modifiers.append("追い風")
        
        # まひ
        if pokemon.get("status") == "par":
            effective_speed = int(effective_speed * 0.5)
            modifiers.append("まひ")
        
        return SpeedEntry(
            name=name,
            species=name,
            effective_speed=int(effective_speed),
            is_player=is_player,
            raw_speed=base_speed,
            modifiers=modifiers,
        )


# Singleton
_speed_calculator = None

def get_speed_calculator() -> SpeedCalculator:
    global _speed_calculator
    if _speed_calculator is None:
        _speed_calculator = SpeedCalculator()
    return _speed_calculator
