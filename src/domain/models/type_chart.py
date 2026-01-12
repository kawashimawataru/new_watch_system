"""
Type Chart - タイプ相性表

Gen 9（SV）準拠のタイプ相性を定義するValue Object。
"""

from typing import Dict, List

# 完全なタイプ相性表 (Gen 9 / SV準拠)
# キー: 攻撃側タイプ, 値: {防御側タイプ: 倍率}
# 記載がないものは等倍 (1.0)
TYPE_CHART: Dict[str, Dict[str, float]] = {
    # ノーマル
    "Normal": {
        "Rock": 0.5, 
        "Ghost": 0.0,  # ゴーストに無効
        "Steel": 0.5,
    },
    # ほのお
    "Fire": {
        "Fire": 0.5, 
        "Water": 0.5, 
        "Grass": 2.0, 
        "Ice": 2.0, 
        "Bug": 2.0, 
        "Rock": 0.5, 
        "Dragon": 0.5, 
        "Steel": 2.0,
    },
    # みず
    "Water": {
        "Fire": 2.0, 
        "Water": 0.5, 
        "Grass": 0.5, 
        "Ground": 2.0, 
        "Rock": 2.0, 
        "Dragon": 0.5,
    },
    # でんき
    "Electric": {
        "Water": 2.0, 
        "Electric": 0.5, 
        "Grass": 0.5, 
        "Ground": 0.0,  # じめんに無効
        "Flying": 2.0, 
        "Dragon": 0.5,
    },
    # くさ
    "Grass": {
        "Fire": 0.5, 
        "Water": 2.0, 
        "Grass": 0.5, 
        "Poison": 0.5, 
        "Ground": 2.0, 
        "Flying": 0.5, 
        "Bug": 0.5, 
        "Rock": 2.0, 
        "Dragon": 0.5, 
        "Steel": 0.5,
    },
    # こおり
    "Ice": {
        "Fire": 0.5, 
        "Water": 0.5, 
        "Grass": 2.0, 
        "Ice": 0.5, 
        "Ground": 2.0, 
        "Flying": 2.0, 
        "Dragon": 2.0, 
        "Steel": 0.5,
    },
    # かくとう
    "Fighting": {
        "Normal": 2.0, 
        "Ice": 2.0, 
        "Poison": 0.5, 
        "Flying": 0.5, 
        "Psychic": 0.5, 
        "Bug": 0.5, 
        "Rock": 2.0, 
        "Ghost": 0.0,  # ゴーストに無効
        "Dark": 2.0, 
        "Steel": 2.0, 
        "Fairy": 0.5,
    },
    # どく
    "Poison": {
        "Grass": 2.0, 
        "Poison": 0.5, 
        "Ground": 0.5, 
        "Rock": 0.5, 
        "Ghost": 0.5, 
        "Steel": 0.0,  # はがねに無効
        "Fairy": 2.0,
    },
    # じめん
    "Ground": {
        "Fire": 2.0, 
        "Electric": 2.0, 
        "Grass": 0.5, 
        "Poison": 2.0, 
        "Flying": 0.0,  # ひこうに無効
        "Bug": 0.5, 
        "Rock": 2.0, 
        "Steel": 2.0,
    },
    # ひこう
    "Flying": {
        "Electric": 0.5, 
        "Grass": 2.0, 
        "Fighting": 2.0, 
        "Bug": 2.0, 
        "Rock": 0.5, 
        "Steel": 0.5,
    },
    # エスパー
    "Psychic": {
        "Fighting": 2.0, 
        "Poison": 2.0, 
        "Psychic": 0.5, 
        "Dark": 0.0,  # あくに無効
        "Steel": 0.5,
    },
    # むし
    "Bug": {
        "Fire": 0.5, 
        "Grass": 2.0, 
        "Fighting": 0.5, 
        "Poison": 0.5, 
        "Flying": 0.5, 
        "Psychic": 2.0, 
        "Ghost": 0.5, 
        "Dark": 2.0, 
        "Steel": 0.5, 
        "Fairy": 0.5,
    },
    # いわ
    "Rock": {
        "Fire": 2.0, 
        "Water": 0.5,
        "Grass": 0.5,  # 追加修正
        "Ice": 2.0, 
        "Fighting": 0.5, 
        "Ground": 0.5, 
        "Flying": 2.0, 
        "Bug": 2.0, 
        "Steel": 0.5,
    },
    # ゴースト
    "Ghost": {
        "Normal": 0.0,  # ノーマルに無効
        "Psychic": 2.0, 
        "Ghost": 2.0, 
        "Dark": 0.5,    # あくに半減
    },
    # ドラゴン
    "Dragon": {
        "Dragon": 2.0, 
        "Steel": 0.5, 
        "Fairy": 0.0,  # フェアリーに無効
    },
    # あく
    "Dark": {
        "Fighting": 0.5, 
        "Psychic": 2.0, 
        "Ghost": 2.0, 
        "Dark": 0.5, 
        "Fairy": 0.5,
    },
    # はがね
    "Steel": {
        "Fire": 0.5, 
        "Water": 0.5, 
        "Electric": 0.5, 
        "Ice": 2.0, 
        "Rock": 2.0, 
        "Steel": 0.5, 
        "Fairy": 2.0,
    },
    # フェアリー
    "Fairy": {
        "Fire": 0.5, 
        "Fighting": 2.0, 
        "Poison": 0.5, 
        "Dragon": 2.0, 
        "Dark": 2.0, 
        "Steel": 0.5,
    },
}

# タイプ名の日本語マッピング
TYPE_NAMES_JP: Dict[str, str] = {
    "Normal": "ノーマル",
    "Fire": "ほのお",
    "Water": "みず",
    "Electric": "でんき",
    "Grass": "くさ",
    "Ice": "こおり",
    "Fighting": "かくとう",
    "Poison": "どく",
    "Ground": "じめん",
    "Flying": "ひこう",
    "Psychic": "エスパー",
    "Bug": "むし",
    "Rock": "いわ",
    "Ghost": "ゴースト",
    "Dragon": "ドラゴン",
    "Dark": "あく",
    "Steel": "はがね",
    "Fairy": "フェアリー",
}


def normalize_type_name(type_name: str) -> str:
    """
    タイプ名を正規化（大文字小文字、日本語対応）
    """
    if not type_name:
        return ""
    
    # 日本語→英語変換
    jp_to_en = {v: k for k, v in TYPE_NAMES_JP.items()}
    
    # 日本語の場合は英語に変換
    if type_name in jp_to_en:
        return jp_to_en[type_name]
    
    # 英語の場合は先頭大文字に正規化
    return type_name.capitalize()


def get_type_effectiveness(move_type: str, defender_types: List[str]) -> float:
    """
    攻撃のタイプ相性を計算する
    
    Args:
        move_type: 技のタイプ
        defender_types: 防御側のタイプ一覧
        
    Returns:
        float: ダメージ倍率 (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
    """
    if not move_type or not defender_types:
        return 1.0
    
    # タイプ名を正規化
    move_type = normalize_type_name(move_type)
    
    effectiveness = 1.0
    
    for def_type in defender_types:
        def_type = normalize_type_name(def_type)
        if move_type in TYPE_CHART and def_type in TYPE_CHART[move_type]:
            effectiveness *= TYPE_CHART[move_type][def_type]
    
    return effectiveness


def get_effectiveness_label(effectiveness: float) -> str:
    """
    倍率からラベルを取得
    """
    if effectiveness == 0.0:
        return "無効"
    elif effectiveness < 0.5:
        return "ほとんど効かない"
    elif effectiveness < 1.0:
        return "いまひとつ"
    elif effectiveness == 1.0:
        return "等倍"
    elif effectiveness < 4.0:
        return "効果ばつぐん"
    else:
        return "効果ばつぐん（4倍）"
