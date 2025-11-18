"""
Fast-Lane戦略エンジン (LightGBM)

10ms以内で即時勝率推定を実現する軽量モデル。
Phase 1では基本的な特徴量のみを使用し、高速推論を優先。

Usage:
    strategist = FastStrategist.load("models/fast_lane.pkl")
    win_rate = strategist.predict(battle_state)
"""

import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from predictor.core.models import BattleState


@dataclass
class FastPrediction:
    """
    Fast-Laneの予測結果
    
    Attributes:
        p1_win_rate: P1の勝率 (0.0 ~ 1.0)
        inference_time_ms: 推論時間 (ミリ秒)
        feature_count: 使用した特徴量数
    """
    p1_win_rate: float
    inference_time_ms: float
    feature_count: int


class FastStrategist:
    """
    Fast-Lane戦略エンジン
    
    LightGBMを使用した高速勝率推定モデル。
    Phase 1では基本特徴量 (HP, fainted, weather, etc.) のみを使用。
    
    Performance Target:
    - 推論時間: < 10ms
    - メモリ: < 10MB
    - 精度: 60%+ (Phase 1目標)
    """
    
    def __init__(
        self,
        model: Optional[lgb.Booster] = None,
        feature_names: Optional[List[str]] = None
    ):
        """
        Args:
            model: 訓練済みLightGBMモデル
            feature_names: 特徴量名リスト (順序重要)
        """
        self.model = model
        self.feature_names = feature_names or []
        
    @classmethod
    def train(
        cls,
        training_csv: Path,
        test_size: float = 0.2,
        params: Optional[Dict[str, Any]] = None
    ) -> "FastStrategist":
        """
        訓練データからモデルを構築
        
        Args:
            training_csv: 特徴量CSVファイル (extract_features.pyの出力)
            test_size: テストデータの割合 (デフォルト: 0.2)
            params: LightGBMハイパーパラメータ (Noneの場合はデフォルト)
            
        Returns:
            訓練済みFastStrategist
        """
        print("=" * 60)
        print("🚀 Fast-Lane 訓練開始")
        print("=" * 60)
        
        # データ読み込み
        print(f"\n📂 データ読み込み: {training_csv}")
        df = pd.read_csv(training_csv)
        print(f"   - サンプル数: {len(df)}")
        print(f"   - P1勝率: {df['p1_win'].mean()*100:.1f}%")
        
        # 特徴量とターゲットを分離
        feature_cols = [
            "turn",
            "rating",
            "p1_total_hp",
            "p2_total_hp",
            "hp_difference",
            "p1_fainted",
            "p2_fainted",
            "fainted_difference",
            "has_weather",
            "has_terrain",
            "has_trick_room",
            "p1_active_count",
            "p2_active_count",
        ]
        
        X = df[feature_cols]
        y = df["p1_win"]
        
        print(f"\n🔧 特徴量: {len(feature_cols)}個")
        for col in feature_cols:
            print(f"   - {col}")
        
        # Train/Test分割
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        print(f"\n📊 データ分割:")
        print(f"   - Train: {len(X_train)}サンプル (P1勝率: {y_train.mean()*100:.1f}%)")
        print(f"   - Test:  {len(X_test)}サンプル (P1勝率: {y_test.mean()*100:.1f}%)")
        
        # LightGBM Dataset作成
        train_data = lgb.Dataset(X_train, label=y_train)
        test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
        
        # ハイパーパラメータ
        if params is None:
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "random_state": 42,
            }
        
        print(f"\n⚙️  LightGBM訓練中...")
        print(f"   - Objective: {params['objective']}")
        print(f"   - Num Leaves: {params['num_leaves']}")
        print(f"   - Learning Rate: {params['learning_rate']}")
        
        # 訓練
        model = lgb.train(
            params,
            train_data,
            num_boost_round=100,
            valid_sets=[train_data, test_data],
            valid_names=["train", "test"],
            callbacks=[
                lgb.early_stopping(stopping_rounds=10),
                lgb.log_evaluation(period=20),
            ],
        )
        
        # 評価
        y_pred_proba = model.predict(X_test, num_iteration=model.best_iteration)
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        accuracy = (y_pred == y_test).mean()
        print(f"\n✅ 訓練完了")
        print(f"   - Accuracy: {accuracy*100:.1f}%")
        print(f"   - Best Iteration: {model.best_iteration}")
        
        # 特徴量重要度
        importance = model.feature_importance(importance_type="gain")
        importance_df = pd.DataFrame({
            "feature": feature_cols,
            "importance": importance
        }).sort_values("importance", ascending=False)
        
        print(f"\n📊 特徴量重要度 (Top 5):")
        for _, row in importance_df.head(5).iterrows():
            print(f"   - {row['feature']}: {row['importance']:.0f}")
        
        return cls(model=model, feature_names=feature_cols)
    
    def predict(
        self,
        battle_state: BattleState
    ) -> FastPrediction:
        """
        対戦状態から勝率を予測
        
        Args:
            battle_state: 現在の対戦状態
            
        Returns:
            FastPrediction (勝率 + 推論時間)
        """
        if self.model is None:
            raise ValueError("モデルが未訓練です。train()またはload()を実行してください")
        
        start_time = time.perf_counter()
        
        # BattleStateから特徴量を抽出
        features = self._extract_features_from_state(battle_state)
        
        # DataFrameに変換 (列順序を維持)
        feature_dict = {name: [features[name]] for name in self.feature_names}
        X = pd.DataFrame(feature_dict)
        
        # 予測
        p1_win_rate = self.model.predict(X, num_iteration=self.model.best_iteration)[0]
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return FastPrediction(
            p1_win_rate=float(p1_win_rate),
            inference_time_ms=elapsed_ms,
            feature_count=len(self.feature_names)
        )
    
    def _extract_features_from_state(
        self,
        state: BattleState
    ) -> Dict[str, float]:
        """
        BattleStateから特徴量を抽出
        
        Args:
            state: 対戦状態
            
        Returns:
            特徴量辞書 (feature_name -> value)
        """
        # HP合計を計算
        p1_total_hp = sum(
            p.hp_fraction for p in state.player_a.active if p.hp_fraction > 0
        )
        p2_total_hp = sum(
            p.hp_fraction for p in state.player_b.active if p.hp_fraction > 0
        )
        
        # 倒れたポケモン数 (HP=0のポケモン)
        p1_fainted = sum(
            1 for p in state.player_a.active if p.hp_fraction == 0
        )
        p2_fainted = sum(
            1 for p in state.player_b.active if p.hp_fraction == 0
        )
        
        # アクティブポケモン数
        p1_active_count = len([p for p in state.player_a.active if p.hp_fraction > 0])
        p2_active_count = len([p for p in state.player_b.active if p.hp_fraction > 0])
        
        return {
            "turn": float(state.turn),
            "rating": 1500.0,  # Phase 1ではデフォルト値
            "p1_total_hp": p1_total_hp,
            "p2_total_hp": p2_total_hp,
            "hp_difference": (p1_total_hp - p2_total_hp) / 2.0,
            "p1_fainted": float(p1_fainted),
            "p2_fainted": float(p2_fainted),
            "fainted_difference": float(p2_fainted - p1_fainted),
            "has_weather": 1.0 if state.weather else 0.0,
            "has_terrain": 1.0 if state.terrain else 0.0,
            "has_trick_room": 0.0,  # Phase 1では未実装
            "p1_active_count": float(p1_active_count),
            "p2_active_count": float(p2_active_count),
        }
    
    def save(self, filepath: Path):
        """
        モデルを保存
        
        Args:
            filepath: 保存先パス (.pkl)
        """
        if self.model is None:
            raise ValueError("モデルが未訓練です")
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "wb") as f:
            pickle.dump({
                "model": self.model,
                "feature_names": self.feature_names,
            }, f)
        
        print(f"💾 モデル保存: {filepath}")
        print(f"   サイズ: {filepath.stat().st_size / 1024:.1f} KB")
    
    @classmethod
    def load(cls, filepath: Path) -> "FastStrategist":
        """
        モデルを読み込み
        
        Args:
            filepath: モデルファイルパス (.pkl)
            
        Returns:
            FastStrategist
        """
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        
        print(f"📂 モデル読み込み: {filepath}")
        print(f"   特徴量数: {len(data['feature_names'])}")
        
        return cls(
            model=data["model"],
            feature_names=data["feature_names"]
        )
