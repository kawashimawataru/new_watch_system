#!/usr/bin/env python3
"""
高レート帯VGCリプレイ収集スクリプト (1500+特化)

Pokemon Showdownから高レート帯(1500+)のVGCリプレイを効率的に収集します。
通常の検索APIではレート指定ができないため、大量にダウンロードしてフィルタリングします。

使用方法:
    python scripts/download_high_rating_replays.py --target 200 --min-rating 1500
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import aiohttp


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class HighRatingReplayCollector:
    """高レート帯リプレイ専用コレクター"""
    
    BASE_URL = "https://replay.pokemonshowdown.com"
    
    # 全VGCレギュレーション (レート問わず収集)
    VGC_FORMATS = [
        "gen9vgc2025regj",      # 最新 (2025年10月～)
        "gen9vgc2025regi",      # 2025年7～9月
        "gen9vgc2025regh",      # 2025年前半
        "gen9vgc2024regg",      # 2024年
        "gen9vgc2023regd",      # 2023年後半
        "gen9vgc2023regc",      # 2023年前半
    ]
    
    def __init__(self, min_rating: int = 1500, target_count: int = 200):
        """
        Args:
            min_rating: 最低レーティング
            target_count: 収集目標数
        """
        self.min_rating = min_rating
        self.target_count = target_count
        self.collected_replays = []
        self.downloaded_count = 0
        self.filtered_count = 0
        self.rating_distribution = {
            "1500-1600": 0,
            "1600-1700": 0,
            "1700-1800": 0,
            "1800+": 0,
        }
    
    async def search_replays(
        self,
        session: aiohttp.ClientSession,
        format_id: str,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """リプレイ検索"""
        url = f"{self.BASE_URL}/search.json"
        params = {"format": format_id, "page": page}
        
        try:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                return data if isinstance(data, list) else []
                
        except Exception as e:
            logger.debug(f"検索エラー ({format_id}, page {page}): {e}")
            return []
    
    async def download_replay_detail(
        self,
        session: aiohttp.ClientSession,
        replay_id: str
    ) -> Dict[str, Any] | None:
        """リプレイ詳細をダウンロードしてフィルタリング"""
        url = f"{self.BASE_URL}/{replay_id}.json"
        
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                rating = data.get("rating")
                
                self.downloaded_count += 1
                
                # レーティングフィルタ
                if rating is None or rating < self.min_rating:
                    self.filtered_count += 1
                    return None
                
                # レーティング分布を記録
                if rating >= 1800:
                    self.rating_distribution["1800+"] += 1
                elif rating >= 1700:
                    self.rating_distribution["1700-1800"] += 1
                elif rating >= 1600:
                    self.rating_distribution["1600-1700"] += 1
                else:
                    self.rating_distribution["1500-1600"] += 1
                
                if len(self.collected_replays) % 10 == 0 and len(self.collected_replays) > 0:
                    logger.info(
                        f"✅ 進捗: {len(self.collected_replays)}/{self.target_count} "
                        f"(Rating: {rating}, DL: {self.downloaded_count}, "
                        f"除外: {self.filtered_count})"
                    )
                
                return {
                    "id": replay_id,
                    "format": data.get("format"),
                    "rating": rating,
                    "uploadtime": data.get("uploadtime"),
                    "log": data.get("log", ""),
                    "players": data.get("players", []),
                    "winner": data.get("winner"),
                }
                
        except Exception as e:
            logger.debug(f"ダウンロード失敗 ({replay_id}): {e}")
            return None
    
    async def collect_high_rating_replays(
        self,
        max_concurrent: int = 20,
        max_pages_per_format: int = 30
    ) -> List[Dict[str, Any]]:
        """
        高レート帯リプレイを収集
        
        戦略:
        1. 複数フォーマットから並列検索
        2. 大量にダウンロードしてレートでフィルタ
        3. 目標数に達したら終了
        """
        logger.info(f"🎯 目標: レート{self.min_rating}+のリプレイを{self.target_count}件収集")
        
        async with aiohttp.ClientSession() as session:
            format_pages = {fmt: 1 for fmt in self.VGC_FORMATS}
            
            while len(self.collected_replays) < self.target_count:
                # 各フォーマットから検索
                search_tasks = []
                for format_id in self.VGC_FORMATS:
                    if format_pages[format_id] <= max_pages_per_format:
                        search_tasks.append(
                            self.search_replays(session, format_id, format_pages[format_id])
                        )
                        format_pages[format_id] += 1
                
                if not search_tasks:
                    logger.warning("⚠️  検索可能なページがありません")
                    break
                
                # 並列検索
                search_results = await asyncio.gather(*search_tasks)
                
                # リプレイIDを収集
                replay_ids = []
                for replays in search_results:
                    for item in replays:
                        replay_id = item.get("id", "")
                        if replay_id:
                            replay_ids.append(replay_id)
                
                if not replay_ids:
                    break
                
                logger.info(f"📥 {len(replay_ids)}件のリプレイをチェック中...")
                
                # 並列ダウンロード (レートフィルタリング)
                download_tasks = []
                for replay_id in replay_ids:
                    if len(self.collected_replays) >= self.target_count:
                        break
                    download_tasks.append(
                        self.download_replay_detail(session, replay_id)
                    )
                
                # バッチ実行
                for i in range(0, len(download_tasks), max_concurrent):
                    batch = download_tasks[i:i+max_concurrent]
                    results = await asyncio.gather(*batch)
                    
                    for replay_data in results:
                        if replay_data:
                            self.collected_replays.append(replay_data)
                            
                            if len(self.collected_replays) >= self.target_count:
                                break
                    
                    # レート制限対策
                    await asyncio.sleep(0.5)
                
                if len(self.collected_replays) >= self.target_count:
                    break
        
        return self.collected_replays
    
    def save_replays(self, output_dir: Path):
        """リプレイを保存"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vgc_high_rating_{self.min_rating}plus_{timestamp}.json"
        filepath = output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.collected_replays, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 保存: {filepath} ({len(self.collected_replays)}件)")
    
    def print_statistics(self):
        """統計情報を表示"""
        logger.info("\n" + "="*60)
        logger.info("📊 収集統計")
        logger.info("="*60)
        logger.info(f"目標: {self.target_count}件 (レート{self.min_rating}+)")
        logger.info(f"収集成功: {len(self.collected_replays)}件")
        logger.info(f"ダウンロード総数: {self.downloaded_count}件")
        logger.info(f"レートフィルタで除外: {self.filtered_count}件")
        logger.info(f"採用率: {len(self.collected_replays)/max(self.downloaded_count,1)*100:.1f}%")
        logger.info("\nレーティング分布:")
        for range_name, count in self.rating_distribution.items():
            if count > 0:
                logger.info(f"  {range_name}: {count}件")


async def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="高レート帯VGCリプレイ収集 (1500+特化)"
    )
    parser.add_argument(
        "--target",
        type=int,
        default=200,
        help="収集目標数 (デフォルト: 200)"
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        default=1500,
        help="最低レーティング (デフォルト: 1500)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/replays"),
        help="保存先ディレクトリ (デフォルト: data/replays)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=20,
        help="最大同時ダウンロード数 (デフォルト: 20)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=30,
        help="各フォーマットの最大ページ数 (デフォルト: 30)"
    )
    
    args = parser.parse_args()
    
    logger.info("="*70)
    logger.info("🚀 高レート帯VGCリプレイ収集")
    logger.info("="*70)
    logger.info(f"目標件数: {args.target}件")
    logger.info(f"最低レーティング: {args.min_rating}")
    logger.info(f"保存先: {args.output}")
    logger.info("")
    
    collector = HighRatingReplayCollector(
        min_rating=args.min_rating,
        target_count=args.target
    )
    
    try:
        # 収集実行
        replays = await collector.collect_high_rating_replays(
            max_concurrent=args.concurrent,
            max_pages_per_format=args.max_pages
        )
        
        # 保存
        if replays:
            collector.save_replays(args.output)
        
        # 統計表示
        collector.print_statistics()
        
        logger.info("\n✅ 収集完了！")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  ユーザーによって中断されました")
        logger.info(f"収集済み: {len(collector.collected_replays)}件")
        
        # 中断時も保存
        if collector.collected_replays:
            collector.save_replays(args.output)
    
    except Exception as e:
        logger.error(f"\n❌ エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
