# 2025-11-17 Showdown データ整合アップデート

## 1. 技・ポケモン・道具データの同期

- `scripts/fetch_showdown_data.py` に items.js のダウンロードと JSON 変換を追加し、Pokédex / Moves / Items / Type Chart をワンコマンドで最新化できるようにした。
- `scripts/verify_showdown_data.py` を新規追加。Upstream の JS を一時的に取得し、ローカル JSON と完全一致するか比較する仕組みを用意した。差分があれば exit code 1 とともに再取得を促す。
- `predictor/data/showdown_loader.py` で MoveEntry に shortDesc / desc / flags を取り込み、ItemEntry を新設して `get_item` 経由でアクセスできるようにした。

## 2. 技効果・ターゲットメタデータの付与

- `predictor/engine/move_metadata.py` を実装し、BattleState の legal_actions へ Showdown 由来の完全な move metadata（タイプ・カテゴリ・威力・命中・priority・flags・target）を注入。
- Showdown の target 文字列を `self` / `ally` / `spread` など UI/スコアリングで扱いやすい形へ正規化し、ターゲット指定が抜けているログでも自動補完できるようにした。
- `predictor/core/position_evaluator.py` で `StateRebuilder` → `apply_move_metadata` → EV 更新 → DamageAnnotator と流れるようにし、常に最新の Showdown 情報を参照。

## 3. テストとドキュメント

- `tests/test_move_metadata.py` を追加し、Protect の self ターゲット化や Rock Slide の spread 化、Extreme Speed の priority 反映などを自動検証。
- `docs/startup_guide.md` に「Showdown データ同期」節を追加し、`fetch_showdown_data.py` / `verify_showdown_data.py` の運用手順を明記。

## 4. 今後の着手ポイント

1. `DamageCalculator` を Showdown 計算式と突き合わせ、items/move flags (例: Sheer Force, Punching Glove) を活用して一致性を高める。
2. `StateRebuilder` で legal_actions に含まれる move id を Showdown のアクションログに合わせた schema へ拡張し、ターン順/優先度の整合性テストを追加。
3. `scripts/verify_showdown_data.py` を CI へ組み込み、データ更新忘れを自動検知する。

上記状況により、「技/ポケモン/道具を Showdown と一致させる」という最優先事項をデータレベルで担保できるようになった。次は技効果・ターゲットの挙動をさらに洗練し、ダメージ計算の一致度向上に着手する。
