"use client";

import { useState, useEffect, useRef } from "react";
import { WinRatePoint } from "@/components/WinRateChart";

interface PlayerInfo {
    name: string;
    rating: number;
    pokemon: string[];
}

interface GameState {
    turn: number;
    winRate: number;
    p1: PlayerInfo;
    p2: PlayerInfo;
}

interface UseGameStateReturn {
    isConnected: boolean;
    gameState: GameState | null;
    winRateHistory: WinRatePoint[];
}

const WEBSOCKET_URL = "ws://localhost:8000/ws/spectator";

export function useGameState(): UseGameStateReturn {
    const [isConnected, setIsConnected] = useState(false);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [winRateHistory, setWinRateHistory] = useState<WinRatePoint[]>([]);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        connect();
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, []);

    const connect = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        console.log("Connecting to WebSocket...", WEBSOCKET_URL);
        const ws = new WebSocket(WEBSOCKET_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("WebSocket Connected");
            setIsConnected(true);
        };

        ws.onclose = () => {
            console.log("WebSocket Disconnected");
            setIsConnected(false);
            // 再接続試行 (3秒後)
            reconnectTimeoutRef.current = setTimeout(() => {
                connect();
            }, 3000);
        };



        ws.onerror = (error) => {
            // Keep error log quiet for connection refused (common during startup)
            console.warn("WebSocket Connection Error (Server likely offline)");
            ws.close(); // Triggers onclose
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === "game_update") {
                    const data = message.data as GameState;
                    setGameState(data);

                    // 勝率履歴更新
                    setWinRateHistory((prev) => {
                        // 同じターンのデータが既にあれば更新、なければ追加
                        const existingIndex = prev.findIndex((p) => p.turn === data.turn);
                        if (existingIndex !== -1) {
                            const newHistory = [...prev];
                            newHistory[existingIndex] = { turn: data.turn, winRate: data.winRate };
                            return newHistory;
                        } else {
                            return [...prev, { turn: data.turn, winRate: data.winRate }].sort((a, b) => a.turn - b.turn);
                        }
                    });
                }
            } catch (e) {
                console.error("Message Parse Error:", e);
            }
        };
    };

    return {
        isConnected,
        gameState,
        winRateHistory,
    };
}
