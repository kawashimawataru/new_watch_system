"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import {
    Sun, Cloud, Snowflake, Wind,
    Zap, Sparkles, Leaf, Shield,
    Flame, Droplets, Activity
} from "lucide-react";

interface BattleConditions {
    weather?: "sun" | "rain" | "sand" | "snow" | null;
    terrain?: "electric" | "grassy" | "psychic" | "misty" | null;

    playerTailwind?: boolean;
    opponentTailwind?: boolean;
    trickRoom?: boolean;

    playerReflect?: boolean;
    playerLightScreen?: boolean;
    opponentReflect?: boolean;
    opponentLightScreen?: boolean;
}

interface BattleConditionsPanelProps {
    conditions: BattleConditions;
    className?: string;
}

const WeatherIcon: React.FC<{ weather: string | null | undefined }> = ({ weather }) => {
    switch (weather) {
        case "sun": return <Sun className="w-4 h-4 text-orange-400" />;
        case "rain": return <Droplets className="w-4 h-4 text-blue-400" />;
        case "sand": return <Wind className="w-4 h-4 text-yellow-600" />;
        case "snow": return <Snowflake className="w-4 h-4 text-cyan-300" />;
        default: return <Cloud className="w-4 h-4 text-gray-400" />;
    }
};

const TerrainIcon: React.FC<{ terrain: string | null | undefined }> = ({ terrain }) => {
    switch (terrain) {
        case "electric": return <Zap className="w-4 h-4 text-yellow-400" />;
        case "grassy": return <Leaf className="w-4 h-4 text-green-400" />;
        case "psychic": return <Sparkles className="w-4 h-4 text-pink-400" />;
        case "misty": return <Cloud className="w-4 h-4 text-purple-300" />;
        default: return null;
    }
};

const weatherLabels: Record<string, string> = {
    sun: "にほんばれ",
    rain: "あめ",
    sand: "すなあらし",
    snow: "ゆき",
};

const terrainLabels: Record<string, string> = {
    electric: "エレキフィールド",
    grassy: "グラスフィールド",
    psychic: "サイコフィールド",
    misty: "ミストフィールド",
};

export const BattleConditionsPanel: React.FC<BattleConditionsPanelProps> = ({
    conditions,
    className
}) => {
    const hasAnyCondition = conditions.weather || conditions.terrain ||
        conditions.playerTailwind || conditions.opponentTailwind ||
        conditions.trickRoom || conditions.playerReflect ||
        conditions.playerLightScreen || conditions.opponentReflect ||
        conditions.opponentLightScreen;

    if (!hasAnyCondition) return null;

    return (
        <motion.div
            className={cn(
                "flex flex-wrap gap-2 p-2 bg-black/40 border border-white/10 rounded-lg backdrop-blur-sm",
                className
            )}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
        >
            {/* Weather */}
            {conditions.weather && (
                <div className={cn(
                    "flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold",
                    conditions.weather === "sun" && "bg-orange-500/20 text-orange-300 border border-orange-500/30",
                    conditions.weather === "rain" && "bg-blue-500/20 text-blue-300 border border-blue-500/30",
                    conditions.weather === "sand" && "bg-yellow-600/20 text-yellow-400 border border-yellow-600/30",
                    conditions.weather === "snow" && "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                )}>
                    <WeatherIcon weather={conditions.weather} />
                    <span>{weatherLabels[conditions.weather]}</span>
                </div>
            )}

            {/* Terrain */}
            {conditions.terrain && (
                <div className={cn(
                    "flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold",
                    conditions.terrain === "electric" && "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30",
                    conditions.terrain === "grassy" && "bg-green-500/20 text-green-300 border border-green-500/30",
                    conditions.terrain === "psychic" && "bg-pink-500/20 text-pink-300 border border-pink-500/30",
                    conditions.terrain === "misty" && "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                )}>
                    <TerrainIcon terrain={conditions.terrain} />
                    <span>{terrainLabels[conditions.terrain]}</span>
                </div>
            )}

            {/* Trick Room */}
            {conditions.trickRoom && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold bg-purple-900/30 text-purple-300 border border-purple-500/30">
                    <Activity className="w-4 h-4" />
                    <span>トリックルーム</span>
                </div>
            )}

            {/* Tailwind */}
            {conditions.playerTailwind && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold bg-green-900/30 text-green-300 border border-green-500/30">
                    <Wind className="w-4 h-4" />
                    <span>追い風(味方)</span>
                </div>
            )}
            {conditions.opponentTailwind && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold bg-red-900/30 text-red-300 border border-red-500/30">
                    <Wind className="w-4 h-4" />
                    <span>追い風(相手)</span>
                </div>
            )}

            {/* Screens */}
            {(conditions.playerReflect || conditions.playerLightScreen) && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold bg-green-800/30 text-green-200 border border-green-600/30">
                    <Shield className="w-4 h-4" />
                    <span>
                        壁(味方)
                        {conditions.playerReflect && <span className="ml-1 text-orange-300">物</span>}
                        {conditions.playerLightScreen && <span className="ml-1 text-blue-300">特</span>}
                    </span>
                </div>
            )}
            {(conditions.opponentReflect || conditions.opponentLightScreen) && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold bg-red-800/30 text-red-200 border border-red-600/30">
                    <Shield className="w-4 h-4" />
                    <span>
                        壁(相手)
                        {conditions.opponentReflect && <span className="ml-1 text-orange-300">物</span>}
                        {conditions.opponentLightScreen && <span className="ml-1 text-blue-300">特</span>}
                    </span>
                </div>
            )}
        </motion.div>
    );
};

export default BattleConditionsPanel;
