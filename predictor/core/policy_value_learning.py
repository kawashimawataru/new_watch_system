"""
Policy/Value Learning: Metamon式オフライン学習

ログから Policy（行動分布）と Value（勝率）を学習する。

研究参照:
- Metamon: https://arxiv.org/abs/2504.04395
  - 観戦ログから学習可能な軌跡を作り
  - まず模倣→オフラインRL→自己対戦で微調整

実装フェーズ:
1. データ収集（BattleLog → TrainingExample）
2. Policy学習（行動分類）
3. Value学習（勝率回帰）
"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


# ============================================================================
# データ構造
# ============================================================================

@dataclass
class StateFeatures:
    """
    状態の特徴量ベクトル
    
    オープンチームシート前提なので、全情報を特徴量化できる。
    """
    # 自分のアクティブ（2体）
    self_hp: List[float]  # [slot0_hp, slot1_hp]
    self_status: List[int]  # [slot0_status_code, slot1_status_code]
    self_boosts: List[Dict[str, int]]  # ランク変化
    
    # 相手のアクティブ（2体）
    opp_hp: List[float]
    opp_status: List[int]
    opp_boosts: List[Dict[str, int]]
    
    # 控え情報
    self_reserves: int  # 残り控え数
    opp_reserves: int
    
    # フィールド状態
    weather: int  # 天候コード
    terrain: int  # フィールドコード
    trick_room: int  # 0 or 残りターン
    tailwind_self: int  # 0 or 残りターン
    tailwind_opp: int
    
    # ターン情報
    turn: int
    
    def to_vector(self) -> np.ndarray:
        """特徴量ベクトルに変換"""
        features = []
        
        # HP (4)
        features.extend(self.self_hp)
        features.extend(self.opp_hp)
        
        # Status (4)
        features.extend(self.self_status)
        features.extend(self.opp_status)
        
        # Reserves (2)
        features.append(self.self_reserves)
        features.append(self.opp_reserves)
        
        # Field (5)
        features.append(self.weather)
        features.append(self.terrain)
        features.append(self.trick_room)
        features.append(self.tailwind_self)
        features.append(self.tailwind_opp)
        
        # Turn (1)
        features.append(self.turn)
        
        # Boosts (各6項目 × 4体 = 24)
        boost_keys = ['atk', 'def', 'spa', 'spd', 'spe', 'accuracy']
        for boosts in self.self_boosts + self.opp_boosts:
            for key in boost_keys:
                features.append(boosts.get(key, 0))
        
        return np.array(features, dtype=np.float32)
    
    @staticmethod
    def feature_dim() -> int:
        """特徴量次元数"""
        return 4 + 4 + 2 + 5 + 1 + 24  # = 40


@dataclass
class ActionLabel:
    """
    行動ラベル（Policy学習用）
    
    2体分の行動をエンコード
    """
    slot0_action_id: int  # 行動ID
    slot1_action_id: int
    
    @staticmethod
    def from_joint_action(action: Any, action_vocab: Dict[str, int]) -> 'ActionLabel':
        """JointActionからラベルを作成"""
        slot0_key = f"{action.slot0_action.action_type}:{action.slot0_action.move_or_pokemon}"
        slot1_key = f"{action.slot1_action.action_type}:{action.slot1_action.move_or_pokemon}"
        
        return ActionLabel(
            slot0_action_id=action_vocab.get(slot0_key, 0),
            slot1_action_id=action_vocab.get(slot1_key, 0),
        )


@dataclass
class TrainingExample:
    """学習用サンプル"""
    state: StateFeatures
    action: ActionLabel  # Policy学習用
    outcome: float  # Value学習用（1.0=勝利, 0.0=敗北, 0.5=引き分け）
    side: str  # "p1" or "p2"


@dataclass
class BattleLog:
    """バトルログ（1試合分）"""
    battle_id: str
    format: str
    winner: str  # "p1" or "p2"
    turns: List[TurnLog]
    
    def to_training_examples(self, action_vocab: Dict[str, int]) -> List[TrainingExample]:
        """学習用サンプルに変換"""
        examples = []
        
        for turn in self.turns:
            for side in ["p1", "p2"]:
                state = turn.get_state_features(side)
                action = turn.get_action_label(side, action_vocab)
                outcome = 1.0 if self.winner == side else 0.0
                
                examples.append(TrainingExample(
                    state=state,
                    action=action,
                    outcome=outcome,
                    side=side,
                ))
        
        return examples


@dataclass
class TurnLog:
    """ターンログ"""
    turn: int
    p1_state: Dict[str, Any]
    p2_state: Dict[str, Any]
    p1_action: Optional[Dict[str, Any]]
    p2_action: Optional[Dict[str, Any]]
    
    def get_state_features(self, side: str) -> StateFeatures:
        """状態特徴量を取得"""
        if side == "p1":
            self_state = self.p1_state
            opp_state = self.p2_state
        else:
            self_state = self.p2_state
            opp_state = self.p1_state
        
        return StateFeatures(
            self_hp=self_state.get("hp", [1.0, 1.0]),
            self_status=self_state.get("status", [0, 0]),
            self_boosts=self_state.get("boosts", [{}, {}]),
            opp_hp=opp_state.get("hp", [1.0, 1.0]),
            opp_status=opp_state.get("status", [0, 0]),
            opp_boosts=opp_state.get("boosts", [{}, {}]),
            self_reserves=self_state.get("reserves", 2),
            opp_reserves=opp_state.get("reserves", 2),
            weather=self_state.get("weather", 0),
            terrain=self_state.get("terrain", 0),
            trick_room=self_state.get("trick_room", 0),
            tailwind_self=self_state.get("tailwind", 0),
            tailwind_opp=opp_state.get("tailwind", 0),
            turn=self.turn,
        )
    
    def get_action_label(self, side: str, action_vocab: Dict[str, int]) -> ActionLabel:
        """行動ラベルを取得"""
        if side == "p1":
            action = self.p1_action
        else:
            action = self.p2_action
        
        if not action:
            return ActionLabel(slot0_action_id=0, slot1_action_id=0)
        
        slot0_key = f"{action.get('slot0_type', 'move')}:{action.get('slot0_move', 'tackle')}"
        slot1_key = f"{action.get('slot1_type', 'move')}:{action.get('slot1_move', 'tackle')}"
        
        return ActionLabel(
            slot0_action_id=action_vocab.get(slot0_key, 0),
            slot1_action_id=action_vocab.get(slot1_key, 0),
        )


# ============================================================================
# Policy Model（行動予測）
# ============================================================================

class PolicyModel:
    """
    Policy学習モデル
    
    状態から行動分布を予測（模倣学習）
    """
    
    def __init__(self, action_vocab_size: int = 500):
        self.action_vocab_size = action_vocab_size
        self.model_slot0 = None  # LightGBM for slot0
        self.model_slot1 = None  # LightGBM for slot1
        self.action_vocab: Dict[str, int] = {}
        self.id_to_action: Dict[int, str] = {}
    
    def train(self, examples: List[TrainingExample], **lgb_params):
        """学習"""
        if not HAS_LIGHTGBM:
            print("⚠️ LightGBM not installed, skipping training")
            return
        
        X = np.array([ex.state.to_vector() for ex in examples])
        y_slot0 = np.array([ex.action.slot0_action_id for ex in examples])
        y_slot1 = np.array([ex.action.slot1_action_id for ex in examples])
        
        default_params = {
            "objective": "multiclass",
            "num_class": self.action_vocab_size,
            "metric": "multi_logloss",
            "verbosity": -1,
            "num_leaves": 31,
            "learning_rate": 0.05,
            "n_estimators": 100,
        }
        default_params.update(lgb_params)
        
        print(f"Training Policy (slot0) on {len(examples)} examples...")
        self.model_slot0 = lgb.LGBMClassifier(**default_params)
        self.model_slot0.fit(X, y_slot0)
        
        print(f"Training Policy (slot1) on {len(examples)} examples...")
        self.model_slot1 = lgb.LGBMClassifier(**default_params)
        self.model_slot1.fit(X, y_slot1)
        
        print("✅ Policy training complete")
    
    def predict_proba(self, state: StateFeatures) -> Tuple[np.ndarray, np.ndarray]:
        """行動確率を予測"""
        if self.model_slot0 is None or self.model_slot1 is None:
            # 未学習の場合は一様分布
            uniform = np.ones(self.action_vocab_size) / self.action_vocab_size
            return uniform, uniform
        
        X = state.to_vector().reshape(1, -1)
        proba_slot0 = self.model_slot0.predict_proba(X)[0]
        proba_slot1 = self.model_slot1.predict_proba(X)[0]
        
        return proba_slot0, proba_slot1
    
    def save(self, path: str):
        """モデルを保存"""
        with open(path, 'wb') as f:
            pickle.dump({
                'model_slot0': self.model_slot0,
                'model_slot1': self.model_slot1,
                'action_vocab': self.action_vocab,
                'id_to_action': self.id_to_action,
            }, f)
        print(f"✅ Policy model saved to {path}")
    
    def load(self, path: str):
        """モデルを読み込み"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model_slot0 = data['model_slot0']
            self.model_slot1 = data['model_slot1']
            self.action_vocab = data['action_vocab']
            self.id_to_action = data['id_to_action']
        print(f"✅ Policy model loaded from {path}")


# ============================================================================
# Value Model（勝率予測）
# ============================================================================

class ValueModel:
    """
    Value学習モデル
    
    状態から勝率を予測
    """
    
    def __init__(self):
        self.model = None
    
    def train(self, examples: List[TrainingExample], **lgb_params):
        """学習"""
        if not HAS_LIGHTGBM:
            print("⚠️ LightGBM not installed, skipping training")
            return
        
        X = np.array([ex.state.to_vector() for ex in examples])
        y = np.array([ex.outcome for ex in examples])
        
        default_params = {
            "objective": "binary",
            "metric": "auc",
            "verbosity": -1,
            "num_leaves": 31,
            "learning_rate": 0.05,
            "n_estimators": 100,
        }
        default_params.update(lgb_params)
        
        print(f"Training Value model on {len(examples)} examples...")
        self.model = lgb.LGBMClassifier(**default_params)
        self.model.fit(X, y)
        
        print("✅ Value training complete")
    
    def predict(self, state: StateFeatures) -> float:
        """勝率を予測"""
        if self.model is None:
            return 0.5  # 未学習の場合は0.5
        
        X = state.to_vector().reshape(1, -1)
        proba = self.model.predict_proba(X)[0]
        return proba[1] if len(proba) > 1 else 0.5
    
    def save(self, path: str):
        """モデルを保存"""
        with open(path, 'wb') as f:
            pickle.dump({'model': self.model}, f)
        print(f"✅ Value model saved to {path}")
    
    def load(self, path: str):
        """モデルを読み込み"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
        print(f"✅ Value model loaded from {path}")


# ============================================================================
# ログ収集ユーティリティ
# ============================================================================

class BattleLogCollector:
    """
    バトルログを収集・変換するユーティリティ
    
    Showdownのログから学習用データを生成
    """
    
    def __init__(self, log_dir: str = "data/battle_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.action_vocab: Dict[str, int] = {"unknown": 0}
        self._next_action_id = 1
    
    def register_action(self, action_key: str) -> int:
        """行動を語彙に登録"""
        if action_key not in self.action_vocab:
            self.action_vocab[action_key] = self._next_action_id
            self._next_action_id += 1
        return self.action_vocab[action_key]
    
    def parse_showdown_log(self, log_text: str) -> Optional[BattleLog]:
        """Showdownのログをパース"""
        # TODO: 実際のパース実装
        # ログフォーマット: |turn|1, |move|p1a: Raichu|Thunderbolt|p2a: Gyarados, etc.
        return None
    
    def collect_from_file(self, filepath: str) -> List[TrainingExample]:
        """ファイルからログを収集"""
        try:
            with open(filepath, 'r') as f:
                log_text = f.read()
            
            battle_log = self.parse_showdown_log(log_text)
            if battle_log:
                return battle_log.to_training_examples(self.action_vocab)
        except Exception as e:
            print(f"⚠️ Failed to parse {filepath}: {e}")
        
        return []
    
    def collect_all(self) -> List[TrainingExample]:
        """全ログを収集"""
        examples = []
        for log_file in self.log_dir.glob("*.log"):
            examples.extend(self.collect_from_file(str(log_file)))
        return examples
    
    def save_vocab(self, path: str):
        """語彙を保存"""
        with open(path, 'w') as f:
            json.dump(self.action_vocab, f, indent=2)


# ============================================================================
# 統合トレーナー
# ============================================================================

class MetamonTrainer:
    """
    Metamon式オフライン学習トレーナー
    
    使用方法:
    1. trainer = MetamonTrainer()
    2. trainer.collect_logs("path/to/logs")
    3. trainer.train()
    4. trainer.save_models()
    """
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.collector = BattleLogCollector()
        self.policy_model = PolicyModel()
        self.value_model = ValueModel()
        self.examples: List[TrainingExample] = []
    
    def collect_logs(self, log_dir: str):
        """ログを収集"""
        self.collector.log_dir = Path(log_dir)
        self.examples = self.collector.collect_all()
        print(f"📊 Collected {len(self.examples)} training examples")
    
    def train(self, policy_params: Optional[Dict] = None, value_params: Optional[Dict] = None):
        """学習実行"""
        if not self.examples:
            print("⚠️ No training examples. Run collect_logs() first.")
            return
        
        self.policy_model.action_vocab = self.collector.action_vocab
        self.policy_model.id_to_action = {v: k for k, v in self.collector.action_vocab.items()}
        
        self.policy_model.train(self.examples, **(policy_params or {}))
        self.value_model.train(self.examples, **(value_params or {}))
    
    def save_models(self):
        """モデルを保存"""
        self.policy_model.save(str(self.model_dir / "policy_model.pkl"))
        self.value_model.save(str(self.model_dir / "value_model.pkl"))
        self.collector.save_vocab(str(self.model_dir / "action_vocab.json"))
    
    def load_models(self):
        """モデルを読み込み"""
        self.policy_model.load(str(self.model_dir / "policy_model.pkl"))
        self.value_model.load(str(self.model_dir / "value_model.pkl"))


# ============================================================================
# シングルトン
# ============================================================================

_policy_model: Optional[PolicyModel] = None
_value_model: Optional[ValueModel] = None

def get_policy_model() -> PolicyModel:
    """PolicyModel のシングルトンを取得"""
    global _policy_model
    if _policy_model is None:
        _policy_model = PolicyModel()
        # 学習済みモデルがあれば読み込み
        model_path = Path("models/policy_model.pkl")
        if model_path.exists():
            _policy_model.load(str(model_path))
    return _policy_model

def get_value_model() -> ValueModel:
    """ValueModel のシングルトンを取得"""
    global _value_model
    if _value_model is None:
        _value_model = ValueModel()
        # 学習済みモデルがあれば読み込み
        model_path = Path("models/value_model.pkl")
        if model_path.exists():
            _value_model.load(str(model_path))
    return _value_model
