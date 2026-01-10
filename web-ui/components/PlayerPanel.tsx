"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { motion } from "framer-motion";
import { User } from "lucide-react";

interface PlayerPanelProps {
    name: string;
    rating?: number;
    avatar?: string;
    isSelf?: boolean;
    pokemon?: string[];
    className?: string;
}

export const PlayerPanel: React.FC<PlayerPanelProps> = ({
    name,
    rating,
    avatar,
    isSelf = true,
    pokemon = [],
    className,
}) => {
    // Image Reference Colors
    // Self (Left) -> Green Glow
    // Opponent (Right) -> Light Blue/White Glow
    const mainColor = isSelf ? "border-[#00ff00]" : "border-[#00ffff]";
    const glowColor = isSelf ? "shadow-[0_0_20px_#00ff00]" : "shadow-[0_0_20px_#00ffff]";
    const nameBg = isSelf ? "bg-[#000040]" : "bg-[#000040]"; // Dark blue bg for nameplates

    return (
        <div className={cn("flex flex-col h-full gap-2 relative", className)}>

            {/* Name Plate (Top) */}
            <div className={cn(
                "relative py-1 px-4 rounded-full border-2 border-white/50 text-white font-black italic tracking-wider uppercase text-center shadow-lg w-full flex justify-center items-center z-20",
                nameBg
            )}>
                <span className="drop-shadow-md text-lg">{name}</span>
                <span className="absolute right-3 text-xs font-normal opacity-80 not-italic">選手</span>
            </div>

            {/* Main Camera Frame */}
            <div className={cn(
                "relative flex-1 rounded-xl border-[4px] bg-black/50 overflow-hidden shrink-0 min-h-[160px]",
                mainColor,
                glowColor
            )}>
                {/* Mock Camera Feed / Avatar */}
                {avatar ? (
                    <img src={avatar} alt={name} className="w-full h-full object-cover" />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-[#1a1a1a]">
                        <User className="w-20 h-20 text-gray-700" />
                        <span className="absolute bottom-2 text-xs font-mono text-gray-500">NO SIGNAL</span>
                    </div>
                )}

                {/* Live Indicator */}
                <div className="absolute top-2 left-2 flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-red-600 animate-pulse" />
                    <span className="text-[10px] font-bold text-white shadow-black drop-shadow-md">LIVE</span>
                </div>
            </div>

            {/* Pokemon Team (Vertical on side) */}
            <div className="absolute top-16 bottom-0 w-12 flex flex-col gap-2 z-10 pointer-events-none"
                style={{ [isSelf ? 'right' : 'left']: '-56px' }}
            >
                {pokemon.map((p, i) => (
                    <div key={i} className="w-10 h-10 rounded-full border-2 border-gray-600 bg-gray-900/80 shadow-lg relative overflow-hidden">
                        {/* Placeholder for Pokemon Icon */}
                        <div className="w-full h-full flex items-center justify-center text-[8px] text-gray-400 font-bold overflow-hidden p-1 text-center leading-none">
                            {p.substring(0, 3)}
                        </div>

                        {/* HP Ring (Simulated) */}
                        <svg className="absolute inset-0 w-full h-full -rotate-90">
                            <circle cx="50%" cy="50%" r="45%" fill="none" stroke="#22c55e" strokeWidth="2" strokeDasharray="100" strokeDashoffset="0" />
                        </svg>
                    </div>
                ))}
            </div>

            {/* PokeBalls (Remaining count) */}
            <div className="flex justify-center gap-1 mt-1">
                {[1, 2, 3, 4].map(i => (
                    <div key={i} className={cn(
                        "w-4 h-4 rounded-full border border-gray-500",
                        i <= 2 ? "bg-gradient-to-br from-red-500 to-white" : "bg-gray-800"
                    )} />
                ))}
            </div>

        </div>
    );
};
