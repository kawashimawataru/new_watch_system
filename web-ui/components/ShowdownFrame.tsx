"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";

interface ShowdownFrameProps {
    roomUrl?: string; // Example: https://play.pokemonshowdown.com/battle-gen9vgc2026regf-123456
    className?: string;
}

export const ShowdownFrame: React.FC<ShowdownFrameProps> = ({
    roomUrl = "https://play.pokemonshowdown.com/",
    className,
}) => {
    return (
        <div className={cn("w-full h-full relative group rounded-xl overflow-hidden shadow-2xl bg-black", className)}>
            {/* Iframe */}
            <iframe
                src={roomUrl}
                className="w-full h-full border-0 relative z-10"
                title="Pokemon Showdown"
                sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            />

            {/* Minimal border/glow */}
            <div className="absolute inset-0 border border-white/10 pointer-events-none z-20 rounded-xl" />
        </div>
    );
};
