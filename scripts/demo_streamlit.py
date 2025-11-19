#!/usr/bin/env python3
"""
Streamlit UI デモ用スクリプト

HybridStrategistの動作をCLIでデモ表示
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from predictor.player.hybrid_strategist import HybridStrategist
from predictor.core.models import BattleState, PlayerState, PokemonBattleState


def dict_to_battle_state(battle_dict: dict) -> BattleState:
    """辞書からBattleStateオブジェクトを構築"""
    def parse_pokemon(poke_dict: dict) -> PokemonBattleState:
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


def demo_streamlit_flow():
    """Streamlit UIの動作をCLIでデモ"""
    print("\n" + "=" * 60)
    print("🎮 Streamlit UI デモ")
    print("=" * 60)
    
    # サンプルデータ読み込み
    sample_path = project_root / "frontend/web/public/sample-data.json"
    if not sample_path.exists():
        print(f"❌ サンプルデータが見つかりません: {sample_path}")
        return
    
    with open(sample_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)
    
    battle_log = sample_data.get("battleLog", {})
    battle_state = dict_to_battle_state(battle_log)
    
    print("\n📊 バトル状態:")
    print(f"   Turn: {battle_state.turn}")
    print(f"   Weather: {battle_state.weather}")
    print(f"   Terrain: {battle_state.terrain}")
    print(f"   {battle_state.player_a.name}: {[p.name for p in battle_state.player_a.active]}")
    print(f"   {battle_state.player_b.name}: {[p.name for p in battle_state.player_b.active]}")
    
    # HybridStrategist初期化
    model_path = project_root / "models/fast_lane.pkl"
    if not model_path.exists():
        print(f"\n❌ モデルが見つかりません: {model_path}")
        return
    
    print("\n🔧 HybridStrategist初期化中...")
    strategist = HybridStrategist(
        fast_model_path=str(model_path),
        mcts_rollouts=100
    )
    
    # シミュレーション: Fast-Lane評価ボタン押下
    print("\n" + "=" * 60)
    print("【ユーザー操作】⚡ Fast-Lane評価（即時）ボタンをクリック")
    print("=" * 60)
    
    print("\n⚡ Fast-Lane推論中...")
    fast_result = strategist.predict_quick(battle_state)
    
    print(f"\n✅ Fast-Lane評価完了！({fast_result.inference_time_ms:.2f}ms)")
    print("\n📊 リアルタイム表示タブ:")
    print("┌─────────────────────────────────────┐")
    print("│  ⚡ Fast-Lane 予測結果              │")
    print("├─────────────────────────────────────┤")
    print(f"│  Player A勝率: {fast_result.p1_win_rate:.1%}              │")
    print(f"│  Player B勝率: {(1-fast_result.p1_win_rate):.1%}             │")
    print(f"│  ⚡ FAST prediction                 │")
    print(f"│  🎲 Confidence: {fast_result.confidence:.0%}              │")
    print(f"│  ⏱️  Inference: {fast_result.inference_time_ms:.2f}ms               │")
    print("└─────────────────────────────────────┘")
    
    # シミュレーション: 統合評価ボタン押下
    print("\n" + "=" * 60)
    print("【ユーザー操作】🎯 統合評価（Fast + Slow）ボタンをクリック")
    print("=" * 60)
    
    print("\n🎯 統合評価中（Fast + Slow-Lane）...")
    _, slow_result = strategist.predict_both(battle_state)
    
    print(f"\n✅ 統合評価完了！Fast: {fast_result.inference_time_ms:.2f}ms / Slow: {slow_result.inference_time_ms:.2f}ms")
    print("\n📊 リアルタイム表示タブ（更新後）:")
    print("┌─────────────────────────────────────┐")
    print("│  🎯 Slow-Lane 精密予測結果          │")
    print("├─────────────────────────────────────┤")
    print(f"│  Player A勝率: {slow_result.p1_win_rate:.1%}              │")
    print(f"│  Player B勝率: {(1-slow_result.p1_win_rate):.1%}            │")
    print(f"│  🎯 SLOW prediction                 │")
    print(f"│  🎲 Confidence: {slow_result.confidence:.0%}              │")
    print(f"│  ⏱️  Inference: {slow_result.inference_time_ms:.2f}ms            │")
    print("└─────────────────────────────────────┘")
    
    print("\n📊 Fast vs Slow 比較:")
    print("┌─────────────────────────────────────┐")
    diff = abs(fast_result.p1_win_rate - slow_result.p1_win_rate)
    speedup = slow_result.inference_time_ms / fast_result.inference_time_ms
    agreement = "✅ 一致" if diff < 0.1 else "⚠️ 不一致"
    print(f"│  勝率差: {diff:.1%}                      │")
    print(f"│  速度比: {speedup:.1f}x                     │")
    print(f"│  判定: {agreement}                     │")
    print("└─────────────────────────────────────┘")
    
    print("\n" + "=" * 60)
    print("🎉 Streamlit UI デモ完了！")
    print("=" * 60)
    print("\n💡 実際のUIでは:")
    print("   • http://localhost:8501 でブラウザアクセス")
    print("   • グラフィカルな勝率ゲージ")
    print("   • インタラクティブなPlotlyグラフ")
    print("   • リアルタイムでの結果更新")


if __name__ == "__main__":
    try:
        demo_streamlit_flow()
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
