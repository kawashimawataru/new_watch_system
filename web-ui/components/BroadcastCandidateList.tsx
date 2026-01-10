"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

export interface CandidateMove {
    move1: string; // Action for Slot 1
    move2: string; // Action for Slot 2
    score: number;
    type1: string; // "attack", "protect", "switch"
    type2: string;
    target1?: string;
    target2?: string;
    reasoning?: string;
}

interface BroadcastCandidateListProps {
    candidates: CandidateMove[];
    className?: string;
    title?: string;
    color?: "red" | "blue";
}

export const BroadcastCandidateList: React.FC<BroadcastCandidateListProps> = ({
    candidates,
    className,
    title = "AI 予測",
    color = "red"
}) => {
    const isRed = color === "red";

    return (
        <div className={cn("flex flex-col w-full font-sans", className)}>
            <motion.div
                className="space-y-1.5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
            >
                {candidates.slice(0, 3).map((cand, i) => (
                    <div key={i} className={cn(
                        "flex items-stretch text-white bg-black/60 min-h-[44px] rounded-r text-sm overflow-hidden shadow-sm",
                        "border-l-2",
                        isRed ? "border-l-red-600" : "border-l-blue-600"
                    )}>
                        {/* Percentage */}
                        <div className="w-12 flex flex-col items-center justify-center font-black italic text-yellow-400 bg-black/40 shrink-0 border-r border-white/10">
                            <span className="text-xl leading-none">{cand.score.toFixed(0)}</span>
                            <span className="text-[9px] text-gray-400 leading-none">%</span>
                        </div>

                        {/* Moves Container (Vertical stack for 2 moves) */}
                        <div className="flex-1 flex flex-col justify-center text-[11px] leading-tight">

                            {/* Slot 1 Move */}
                            <div className="flex items-center px-2 py-0.5 border-b border-white/5 bg-white/5">
                                <span className="text-gray-500 font-mono w-4 mr-1">A</span>
                                <span className={cn(
                                    "px-1 rounded text-[9px] font-bold mr-2 w-8 text-center",
                                    cand.type1 === "protect" ? "bg-green-700/80" :
                                        cand.type1 === "switch" ? "bg-blue-700/80" :
                                            "bg-orange-700/80"
                                )}>
                                    {cand.type1 === "protect" ? "守" : cand.type1 === "switch" ? "交" : "攻"}
                                </span>
                                <span className="font-bold text-gray-200 truncate flex-1">
                                    {cand.move1} {cand.target1 && <span className="text-gray-500 text-[9px]">▶ {cand.target1}</span>}
                                </span>
                            </div>

                            {/* Slot 2 Move */}
                            <div className="flex items-center px-2 py-0.5">
                                <span className="text-gray-500 font-mono w-4 mr-1">B</span>
                                <span className={cn(
                                    "px-1 rounded text-[9px] font-bold mr-2 w-8 text-center",
                                    cand.type2 === "protect" ? "bg-green-700/80" :
                                        cand.type2 === "switch" ? "bg-blue-700/80" :
                                            "bg-orange-700/80"
                                )}>
                                    {cand.type2 === "protect" ? "守" : cand.type2 === "switch" ? "交" : "攻"}
                                </span>
                                <span className="font-bold text-gray-200 truncate flex-1">
                                    {cand.move2} {cand.target2 && <span className="text-gray-500 text-[9px]">▶ {cand.target2}</span>}
                                </span>
                            </div>
                        </div>
                    </div>
                ))}
            </motion.div>
        </div>
    );
};
