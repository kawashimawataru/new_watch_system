"""
Smogon Chaos JSONデータの確認スクリプト

実行方法:
    python scripts/check_smogon_data.py
"""

import json
from pathlib import Path

# データ読み込み
data_path = Path(__file__).parent.parent / "data/smogon_stats/gen9vgc2024regh-1760.json"
with open(data_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 70)
print("Smogon Chaos JSON データ確認")
print("=" * 70)
print()

# 基本情報
print(f"総ポケモン数: {len(data['data'])}")
print(f"データ情報: {data.get('info', {})}")
print()

# Flutter Maneの確認
flutter_mane = data['data'].get('Flutter Mane')
if flutter_mane:
    print("🔍 Flutter Mane の統計データ")
    print("-" * 70)
    print()
    
    # 使用率
    print(f"使用率: {flutter_mane.get('usage', 0):.2%}")
    print(f"Raw Count: {flutter_mane.get('Raw count', 0)}")
    print()
    
    # 努力値配分 Top 5
    spreads = flutter_mane.get('Spreads', {})
    print("📊 努力値配分 Top 5:")
    sorted_spreads = sorted(spreads.items(), key=lambda x: x[1], reverse=True)[:5]
    for i, (spread, percentage) in enumerate(sorted_spreads, 1):
        print(f"  {i}. {spread}: {percentage:.2%}")
    print()
    
    # 特性
    abilities = flutter_mane.get('Abilities', {})
    print("✨ 特性:")
    for ability, percentage in sorted(abilities.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {ability}: {percentage:.2%}")
    print()
    
    # 持ち物 Top 5
    items = flutter_mane.get('Items', {})
    print("🎒 持ち物 Top 5:")
    sorted_items = sorted(items.items(), key=lambda x: x[1], reverse=True)[:5]
    for i, (item, percentage) in enumerate(sorted_items, 1):
        print(f"  {i}. {item}: {percentage:.2%}")
    print()
    
    # 技 Top 8
    moves = flutter_mane.get('Moves', {})
    print("⚔️ 技 Top 8:")
    sorted_moves = sorted(moves.items(), key=lambda x: x[1], reverse=True)[:8]
    for i, (move, percentage) in enumerate(sorted_moves, 1):
        print(f"  {i}. {move}: {percentage:.2%}")
    print()
    
    # テラスタイプ
    tera_types = flutter_mane.get('Tera Types', {})
    print("💎 テラスタイプ Top 3:")
    sorted_tera = sorted(tera_types.items(), key=lambda x: x[1], reverse=True)[:3]
    for i, (tera, percentage) in enumerate(sorted_tera, 1):
        print(f"  {i}. {tera}: {percentage:.2%}")
    print()
else:
    print("❌ Flutter Mane がデータに見つかりません")
    print()
    print("利用可能なポケモン (最初の10件):")
    for i, pokemon in enumerate(list(data['data'].keys())[:10], 1):
        print(f"  {i}. {pokemon}")

print()
print("=" * 70)
print("✅ データ確認完了")
print("=" * 70)
