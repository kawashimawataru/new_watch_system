#!/usr/bin/env python3
"""
HybridStrategist UI統合テスト

Streamlit UIでHybridStrategistが正常に動作するかテスト
"""

import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from predictor.player.hybrid_strategist import HybridStrategist
from predictor.core.models import BattleState, PlayerState, PokemonBattleState


def dict_to_battle_state(battle_dict: dict) -> BattleState:
    """辞書からBattleStateオブジェクトを構築"""
    def parse_pokemon(poke_dict: dict) -> PokemonBattleState:
        """Pokemon辞書からPokemonBattleStateを構築"""
        return PokemonBattleState(
            name=poke_dict.get("species", "Unknown"),
            species=poke_dict.get("species"),
            hp_fraction=poke_dict.get("hp", 100) / 100.0,
            status=poke_dict.get("status"),
            boosts=poke_dict.get("boosts", {}),
            item=poke_dict.get("item"),
            ability=poke_dict.get("ability"),
            moves=poke_dict.get("moves", []),
            is_active=True,
            slot=0
        )
    
    p1_data = battle_dict.get("p1", {})
    p2_data = battle_dict.get("p2", {})
    
    player_a = PlayerState(
        name=p1_data.get("name", "Player A"),
        active=[parse_pokemon(p) for p in p1_data.get("active", [])],
        reserves=[r.get("species", "Unknown") for r in p1_data.get("reserves", [])]
    )
    
    player_b = PlayerState(
        name=p2_data.get("name", "Player B"),
        active=[parse_pokemon(p) for p in p2_data.get("active", [])],
        reserves=[r.get("species", "Unknown") for r in p2_data.get("reserves", [])]
    )
    
    return BattleState(
        player_a=player_a,
        player_b=player_b,
        turn=battle_dict.get("turn", 1),
        weather=battle_dict.get("weather"),
        terrain=battle_dict.get("terrain"),
        raw_log=battle_dict
    )


def test_hybrid_with_battle_state():
    """バトル状態でHybridStrategistをテスト"""
    print("=" * 60)
    print("🎮 HybridStrategist UI統合テスト")
    print("=" * 60)
    
    # Fast-Laneモデルのパスを確認
    model_path = project_root / "models/fast_lane.pkl"
    if not model_path.exists():
        print(f"❌ Fast-Laneモデルが見つかりません: {model_path}")
        return False
    
    print(f"✅ Fast-Laneモデル発見: {model_path}")
    
    # バトル状態を読み込み
    battle_state_path = project_root / "tests/data/simple_battle_state.json"
    with open(battle_state_path, "r", encoding="utf-8") as f:
        battle_dict = json.load(f)
    
    # BattleStateオブジェクトに変換
    battle_state = dict_to_battle_state(battle_dict)
    
    print(f"✅ バトル状態読み込み完了")
    print(f"   Turn: {battle_state.turn}")
    print(f"   Weather: {battle_state.weather}")
    print(f"   Terrain: {battle_state.terrain}")
    print(f"   P1 Active: {[p.name for p in battle_state.player_a.active]}")
    print(f"   P2 Active: {[p.name for p in battle_state.player_b.active]}")
    
    # HybridStrategist初期化
    print("\n🔧 HybridStrategist初期化中...")
    strategist = HybridStrategist(
        fast_model_path=str(model_path),
        mcts_rollouts=100  # UI用に高速化
    )
    print("✅ HybridStrategist初期化完了")
    
    # Fast-Lane予測
    print("\n⚡ Fast-Lane予測実行中...")
    fast_result = strategist.predict_quick(battle_state)
    print(f"✅ Fast-Lane予測完了: {fast_result.inference_time_ms:.2f}ms")
    print(f"   P1勝率: {fast_result.p1_win_rate:.1%}")
    print(f"   信頼度: {fast_result.confidence:.1%}")
    print(f"   推奨行動: {fast_result.recommended_action}")
    
    # Slow-Lane予測（同期版）
    print("\n🎯 Slow-Lane予測実行中...")
    fast_result_again, slow_result = strategist.predict_both(battle_state)
    print(f"✅ Slow-Lane予測完了: {slow_result.inference_time_ms:.2f}ms")
    print(f"   P1勝率: {slow_result.p1_win_rate:.1%}")
    print(f"   信頼度: {slow_result.confidence:.1%}")
    print(f"   推奨行動: {slow_result.recommended_action}")
    
    # 比較
    print("\n📊 Fast vs Slow 比較")
    print(f"   勝率差: {abs(fast_result.p1_win_rate - slow_result.p1_win_rate):.1%}")
    speedup = slow_result.inference_time_ms / fast_result.inference_time_ms if fast_result.inference_time_ms > 0 else 0
    print(f"   速度比: {speedup:.1f}x")
    print(f"   判定: {'✅ 一致' if abs(fast_result.p1_win_rate - slow_result.p1_win_rate) < 0.1 else '⚠️ 不一致'}")
    
    print("\n" + "=" * 60)
    print("🎉 HybridStrategist UI統合テスト成功！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_hybrid_with_battle_state()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
