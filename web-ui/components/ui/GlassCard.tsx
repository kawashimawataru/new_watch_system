"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { motion, HTMLMotionProps } from "framer-motion";

interface GlassCardProps extends HTMLMotionProps<"div"> {
    children: React.ReactNode;
    variant?: "default" | "neon-green" | "neon-rose" | "cyber-blue";
    noPadding?: boolean;
}

export const GlassCard: React.FC<GlassCardProps> = ({
    children,
    className,
    variant = "default",
    noPadding = false,
    ...props
}) => {
    const borderColor =
        variant === "neon-green" ? "border-neon-green/30 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]" :
            variant === "neon-rose" ? "border-neon-rose/30 shadow-[0_0_15px_-3px_rgba(244,63,94,0.2)]" :
                variant === "cyber-blue" ? "border-neon-blue/30 shadow-[0_0_15px_-3px_rgba(14,165,233,0.2)]" :
                    "border-white/10";

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
                "relative backdrop-blur-xl bg-black/40 border rounded-xl overflow-hidden",
                borderColor,
                noPadding ? "" : "p-4",
                className
            )}
            {...props}
        >
            {/* Glossy Overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />

            {/* Content */}
            <div className="relative z-10 h-full">
                {children}
            </div>
        </motion.div>
    );
};
