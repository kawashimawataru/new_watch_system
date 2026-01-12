"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { Crosshair, Target, AlertTriangle, Skull } from "lucide-react";

interface DamagePreview {
    moveName: string;
    targetName: string;
    minPercent: number;
    maxPercent: number;
    koChance: number;
    nHitsToKo: number;
    effectivenessText?: string;  // "効果抜群", "今ひとつ", "無効"
}

interface DamagePreviewBadgeProps {
    preview: DamagePreview;
    className?: string;
}

const getKOLabel = (koChance: number, nHits: number): { label: string; color: string; icon: React.ReactNode } => {
    if (koChance >= 1.0) {
        return {
            label: "確定1発",
            color: "bg-red-600 text-white",
            icon: <Skull className="w-3 h-3" />
        };
    }
    if (koChance >= 0.5) {
        return {
            label: `乱数1発 ${(koChance * 100).toFixed(0)}%`,
            color: "bg-orange-600 text-white",
            icon: <AlertTriangle className="w-3 h-3" />
        };
    }
    if (nHits === 2) {
        return {
            label: "確定2発",
            color: "bg-yellow-600 text-white",
            icon: <Target className="w-3 h-3" />
        };
    }
    if (nHits === 3) {
        return {
            label: "確定3発",
            color: "bg-blue-600 text-white",
            icon: <Crosshair className="w-3 h-3" />
        };
    }
    return {
        label: `${nHits}発`,
        color: "bg-gray-600 text-white",
        icon: null
    };
};

export const DamagePreviewBadge: React.FC<DamagePreviewBadgeProps> = ({
    preview,
    className
}) => {
    const { label, color, icon } = getKOLabel(preview.koChance, preview.nHitsToKo);

    return (
        <motion.div
            className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold",
                className
            )}
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
        >
            {/* Damage Range */}
            <span className="text-gray-300">
                {preview.minPercent.toFixed(0)}-{preview.maxPercent.toFixed(0)}%
            </span>

            {/* KO Badge */}
            <span className={cn("flex items-center gap-0.5 px-1.5 py-0.5 rounded", color)}>
                {icon}
                {label}
            </span>

            {/* Effectiveness */}
            {preview.effectivenessText && (
                <span className={cn(
                    "px-1 py-0.5 rounded text-[9px]",
                    preview.effectivenessText === "効果抜群" && "bg-green-700 text-green-100",
                    preview.effectivenessText === "今ひとつ" && "bg-gray-700 text-gray-300",
                    preview.effectivenessText === "無効" && "bg-black text-gray-500"
                )}>
                    {preview.effectivenessText}
                </span>
            )}
        </motion.div>
    );
};

// Status effect badge for burn, paralysis, etc.
interface StatusBadgeProps {
    status: "burn" | "paralysis" | "freeze" | "sleep" | "poison" | "toxic";
    className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
    const statusInfo: Record<string, { label: string; color: string }> = {
        burn: { label: "🔥やけど", color: "bg-orange-700/50 text-orange-200 border-orange-500" },
        paralysis: { label: "⚡まひ", color: "bg-yellow-700/50 text-yellow-200 border-yellow-500" },
        freeze: { label: "❄️こおり", color: "bg-cyan-700/50 text-cyan-200 border-cyan-500" },
        sleep: { label: "💤ねむり", color: "bg-purple-700/50 text-purple-200 border-purple-500" },
        poison: { label: "☠️どく", color: "bg-purple-900/50 text-purple-300 border-purple-600" },
        toxic: { label: "☠️もうどく", color: "bg-purple-900/70 text-purple-200 border-purple-400" },
    };

    const info = statusInfo[status];
    if (!info) return null;

    return (
        <span className={cn(
            "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border",
            info.color,
            className
        )}>
            {info.label}
        </span>
    );
};

// Stat boost badge
interface StatBoostBadgeProps {
    stat: "atk" | "def" | "spa" | "spd" | "spe";
    stages: number;
    className?: string;
}

export const StatBoostBadge: React.FC<StatBoostBadgeProps> = ({ stat, stages, className }) => {
    if (stages === 0) return null;

    const statLabels: Record<string, string> = {
        atk: "攻撃",
        def: "防御",
        spa: "特攻",
        spd: "特防",
        spe: "素早さ",
    };

    const isPositive = stages > 0;

    return (
        <span className={cn(
            "inline-flex items-center px-1 py-0.5 rounded text-[9px] font-bold",
            isPositive ? "bg-green-700/50 text-green-200" : "bg-red-700/50 text-red-200",
            className
        )}>
            {statLabels[stat]} {isPositive ? "+" : ""}{stages}
        </span>
    );
};

export default DamagePreviewBadge;
