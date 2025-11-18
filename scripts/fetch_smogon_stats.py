#!/usr/bin/env python3
"""
Smogon Usage Stats から VGC の統計データ (Chaos JSON) を取得

使用方法:
    python scripts/fetch_smogon_stats.py --output data/smogon_stats
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class SmogonStatsDownloader:
    """Smogon統計データダウンローダー"""
    
    BASE_URL = "https://www.smogon.com/stats/"
    
    # VGC レギュレーション定義（画像より）
    VGC_REGULATIONS = [
        "gen9vgc2023regc",
        "gen9vgc2023regd",
        "gen9vgc2024regg",
        "gen9vgc2025regh",
        "gen9vgc2025regi",
        "gen9vgc2025regj",
        "gen9vgc2026regf",
    ]
    
    def __init__(self, output_dir: str = "data/smogon_stats"):
        """
        Args:
            output_dir: 統計データの保存先ディレクトリ
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
    
    def get_latest_months(self, count: int = 3) -> List[str]:
        """
        最新の統計データ月を取得
        
        Args:
            count: 取得する月数
            
        Returns:
            月のリスト (例: ["2024-12", "2024-11"])
        """
        try:
            response = self.session.get(self.BASE_URL, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ディレクトリリンクから年月を抽出
            months = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                # YYYY-MM/ 形式のディレクトリ
                match = re.match(r'(\d{4}-\d{2})/', href)
                if match:
                    months.append(match.group(1))
            
            # 降順ソートして最新のものを取得
            months = sorted(months, reverse=True)[:count]
            
            logger.info(f"📅 最新の統計月: {months}")
            return months
            
        except Exception as e:
            logger.error(f"月リスト取得エラー: {e}")
            return []
    
    def get_chaos_files(self, year_month: str) -> List[str]:
        """
        指定月のChaos JSONファイルリストを取得
        
        Args:
            year_month: 年月 (例: "2024-12")
            
        Returns:
            ファイル名のリスト
        """
        chaos_url = urljoin(self.BASE_URL, f"{year_month}/chaos/")
        
        try:
            response = self.session.get(chaos_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            files = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                # VGCのJSONファイルのみ
                if any(reg in href for reg in self.VGC_REGULATIONS) and href.endswith('.json'):
                    files.append(href)
            
            logger.info(f"📁 {year_month}/chaos/: {len(files)}件のVGCファイル")
            return files
            
        except Exception as e:
            logger.error(f"Chaosファイルリスト取得エラー ({year_month}): {e}")
            return []
    
    def download_chaos_json(
        self,
        year_month: str,
        filename: str
    ) -> Dict[str, Any] | None:
        """
        Chaos JSONをダウンロード
        
        Args:
            year_month: 年月
            filename: ファイル名
            
        Returns:
            JSONデータ
        """
        url = urljoin(self.BASE_URL, f"{year_month}/chaos/{filename}")
        
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(f"✅ ダウンロード: {filename}")
            return data
            
        except Exception as e:
            logger.error(f"ダウンロードエラー ({filename}): {e}")
            return None
    
    def save_json(
        self,
        data: Dict[str, Any],
        year_month: str,
        filename: str
    ) -> bool:
        """
        JSONを保存
        
        Args:
            data: JSONデータ
            year_month: 年月
            filename: ファイル名
            
        Returns:
            保存成功時 True
        """
        month_dir = self.output_dir / year_month
        month_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = month_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 保存: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存エラー ({filename}): {e}")
            return False
    
    def collect_all_vgc_stats(self, month_count: int = 3) -> int:
        """
        VGCの統計データを収集
        
        Args:
            month_count: 取得する月数
            
        Returns:
            収集成功数
        """
        logger.info("🚀 Smogon VGC統計データ収集開始")
        logger.info(f"   対象レギュレーション: {', '.join(self.VGC_REGULATIONS)}")
        logger.info(f"   保存先: {self.output_dir}")
        
        # 最新の月を取得
        months = self.get_latest_months(month_count)
        
        if not months:
            logger.error("❌ 月リストの取得に失敗")
            return 0
        
        collected = 0
        
        for year_month in months:
            logger.info(f"\n{'='*60}")
            logger.info(f"📅 {year_month} を処理中...")
            logger.info(f"{'='*60}")
            
            # Chaos JSONファイルリストを取得
            files = self.get_chaos_files(year_month)
            
            if not files:
                logger.warning(f"⚠️  {year_month} にVGCファイルが見つかりません")
                continue
            
            # 各ファイルをダウンロード
            for filename in files:
                data = self.download_chaos_json(year_month, filename)
                
                if data:
                    if self.save_json(data, year_month, filename):
                        collected += 1
        
        logger.info(f"\n🎉 収集完了: {collected}件の統計ファイルを保存しました")
        return collected


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="Smogon VGC統計データ取得スクリプト"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/smogon_stats",
        help="保存先ディレクトリ (デフォルト: data/smogon_stats)"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="取得する月数 (デフォルト: 3)"
    )
    
    args = parser.parse_args()
    
    # ダウンローダーを作成して実行
    downloader = SmogonStatsDownloader(output_dir=args.output)
    
    collected = downloader.collect_all_vgc_stats(month_count=args.months)
    
    if collected > 0:
        logger.info(f"\n✅ 完了: {collected}件の統計データを収集しました")
        logger.info(f"📁 保存先: {args.output}")
    else:
        logger.error("\n❌ データの収集に失敗しました")


if __name__ == "__main__":
    main()
