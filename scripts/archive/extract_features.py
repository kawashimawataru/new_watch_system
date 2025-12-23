"""
特徴量抽出スクリプト

760件のリプレイから訓練用データセットを生成する。

Usage:
    python scripts/extract_features.py
    
Output:
    data/training_features.csv (全ターンの特徴量)
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from predictor.player.feature_extractor import FeatureExtractor


def main():
    print("=" * 60)
    print("🚀 Fast-Lane 特徴量抽出開始")
    print("=" * 60)
    
    # リプレイファイルを探す
    replay_dir = Path("data/replays")
    if not replay_dir.exists():
        print("❌ data/replays が見つかりません")
        return
    
    replay_files = list(replay_dir.glob("vgc_replays_*.json"))
    print(f"\n📂 リプレイファイル: {len(replay_files)}件")
    
    if not replay_files:
        print("❌ リプレイファイルが見つかりません")
        return
    
    # 特徴量抽出
    extractor = FeatureExtractor()
    
    print(f"\n⚙️  特徴量抽出中 (2ターン毎にサンプリング)...")
    df = extractor.extract_batch(
        replay_files,
        extract_every_n_turns=2
    )
    
    print(f"\n✅ 抽出完了: {len(df)}サンプル")
    print(f"   - ユニークなリプレイ数: {df['replay_id'].nunique()}")
    print(f"   - 平均ターン数: {df['turn'].mean():.1f}")
    print(f"   - P1勝率: {df['p1_win'].mean()*100:.1f}%")
    print(f"   - 平均レーティング: {df['rating'].mean():.0f}")
    
    # データセット統計
    print("\n📊 特徴量統計:")
    print(f"   - HP差平均: {df['hp_difference'].mean():.3f}")
    print(f"   - 倒れたポケモン差: {df['fainted_difference'].mean():.2f}")
    print(f"   - 天候あり: {df['has_weather'].sum()}ターン ({df['has_weather'].mean()*100:.1f}%)")
    print(f"   - 地形あり: {df['has_terrain'].sum()}ターン ({df['has_terrain'].mean()*100:.1f}%)")
    print(f"   - トリックルーム: {df['has_trick_room'].sum()}ターン ({df['has_trick_room'].mean()*100:.1f}%)")
    
    # 保存
    output_path = Path("data/training_features.csv")
    df.to_csv(output_path, index=False)
    print(f"\n💾 保存完了: {output_path}")
    print(f"   サイズ: {output_path.stat().st_size / 1024:.1f} KB")
    
    # サンプル表示
    print("\n📋 サンプルデータ (先頭5行):")
    print(df.head().to_string(max_cols=8))
    
    print("\n" + "=" * 60)
    print("🎉 特徴量抽出完了！次はLightGBM訓練へ")
    print("=" * 60)


if __name__ == "__main__":
    main()
