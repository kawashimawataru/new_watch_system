"""
Fast-Lane訓練スクリプト

特徴量CSVからLightGBMモデルを訓練し、保存する。

Usage:
    python scripts/train_fast_lane.py
    
Output:
    models/fast_lane.pkl (訓練済みモデル)
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from predictor.player.fast_strategist import FastStrategist


def main():
    # 特徴量CSV
    training_csv = Path("data/training_features.csv")
    
    if not training_csv.exists():
        print("❌ data/training_features.csv が見つかりません")
        print("   先に scripts/extract_features.py を実行してください")
        return
    
    # 訓練
    strategist = FastStrategist.train(
        training_csv=training_csv,
        test_size=0.2
    )
    
    # 保存
    model_path = Path("models/fast_lane.pkl")
    strategist.save(model_path)
    
    print("\n" + "=" * 60)
    print("🎉 Fast-Lane訓練完了！")
    print(f"   モデル: {model_path}")
    print("=" * 60)
    print("\n次のステップ:")
    print("  1. tests/test_fast_strategist.py でテスト実行")
    print("  2. 10ms以内の推論速度を確認")
    print("  3. P1-3-C (統合パイプライン) へ進む")


if __name__ == "__main__":
    main()
