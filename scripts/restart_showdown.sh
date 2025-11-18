#!/bin/bash
# Showdownサーバーを再起動するスクリプト

cd "$(dirname "$0")/../pokemon-showdown" || exit 1

echo "既存のShowdownプロセスを停止中..."
# ポート8000を使っているnodeプロセスを探して停止
PID=$(lsof -iTCP:8000 -sTCP:LISTEN -t 2>/dev/null)
if [ -n "$PID" ]; then
    echo "PID $PID を停止します..."
    kill "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
    sleep 1
fi

echo "Showdownサーバーを起動中..."
node pokemon-showdown start
