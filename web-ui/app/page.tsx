"use client";

import React, { useState, useEffect } from "react";
import { ShowdownFrame } from "@/components/ShowdownFrame";
import { PlayerPanel } from "@/components/PlayerPanel";
import { WinRateBar } from "@/components/WinRateBar";
import { BroadcastCandidateList, CandidateMove } from "@/components/BroadcastCandidateList";
import { ReasoningView } from "@/components/ReasoningView";
import { VisualReasoningView } from "@/components/VisualReasoningView";
import { EffectOverlay, EffectType } from "@/components/EffectOverlay";
import { DebugPad } from "@/components/DebugPad";
import { useGameState } from "@/hooks/useGameState";
import { cn } from "@/lib/utils";
import { BrainCircuit, Presentation, ChartBar } from "lucide-react";

export default function SpectatorPage() {
  const { isConnected, gameState } = useGameState();
  const [showdownUrl, setShowdownUrl] = useState("https://play.pokemonshowdown.com/");
  const [currentEffect, setCurrentEffect] = useState<EffectType>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const [showVisualMode, setShowVisualMode] = useState(false);

  // Mock Update Trigger
  const [mockRefreshKey, setMockRefreshKey] = useState(0);

  useEffect(() => {
    if (currentEffect) {
      const timer = setTimeout(() => setCurrentEffect(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [currentEffect]);

  // Mock data (Japanese)
  const defaultP1 = { name: "カワシマ ワタル", rating: 1530, pokemon: ["テラパゴス", "ガオガエン", "モロバレル", "オーガポン"] };
  const defaultP2 = { name: "エンドウ キワム", rating: 1510, pokemon: ["バドレックス(黒)", "イエッサン♀", "ウーラオス(水)", "トルネロス"] };

  const p1 = gameState?.p1?.name ? gameState.p1 : defaultP1;
  const p2 = gameState?.p2?.name ? gameState.p2 : defaultP2;

  // Mock Candidates P1 (Double Battle Format)
  const mockCandidatesP1: CandidateMove[] = [
    {
      move1: "ドレインパンチ", target1: "バドレックス", type1: "attack",
      move2: "だいちのちから", target2: "ウーラオス", type2: "attack",
      score: 42
    },
    {
      move1: "ねこだまし", target1: "ウーラオス", type1: "protect",
      move2: "テラクラスター", target2: "バドレックス", type2: "attack",
      score: 28
    },
    {
      move1: "交代 -> モロバレル", target1: "", type1: "switch",
      move2: "まもる", target2: "", type2: "protect",
      score: 15
    },
  ];

  // Mock Candidates P2 (Double Battle Format)
  const mockCandidatesP2: CandidateMove[] = [
    {
      move1: "アストラルビット", target1: "全体", type1: "attack",
      move2: "インファイト", target2: "テラパゴス", type2: "attack",
      score: 65
    },
    {
      move1: "まもる", target1: "", type1: "protect",
      move2: "すいりゅうれんだ", target2: "ガオガエン", type2: "attack",
      score: 20
    },
    {
      move1: "アストラルビット", target1: "全体", type1: "attack",
      move2: "守る", target2: "", type2: "protect",
      score: 10
    },
  ];

  const WINRATE_MOCK = 48; // Percentage

  const handleUpdateData = () => {
    setMockRefreshKey(prev => prev + 1);
  };

  return (
    <main className="h-screen w-screen bg-[#080808] text-white overflow-hidden flex flex-col font-sans relative selection:bg-blue-500/30">

      {/* Background Ambience */}
      <div className="absolute inset-0 bg-gradient-radial from-blue-900/10 via-transparent to-transparent pointer-events-none" />

      {/* VFX Overlay */}
      <EffectOverlay effect={currentEffect} />

      {/* Debug Pad */}
      <DebugPad
        onTriggerEffect={setCurrentEffect}
        onUpdateData={handleUpdateData}
      />

      {/* Top Bar (Broadcast Header) */}
      <header className="h-12 shrink-0 bg-gradient-to-r from-black via-gray-900 to-black border-b border-gray-800 flex items-center justify-between px-6 z-50">
        <div className="flex items-center gap-4">
          <img src="/logo.png" className="h-8 w-auto object-contain brightness-150 drop-shadow-[0_0_5px_white]" alt="LOGO" onError={(e) => e.currentTarget.style.display = 'none'} />
          <div className="flex items-center gap-2">
            <div className="px-2 py-0.5 bg-red-600 text-white text-[10px] font-bold tracking-widest uppercase rounded-sm animate-pulse">
              LIVE
            </div>
            <span className="text-sm font-bold tracking-wider text-gray-200" style={{ fontFamily: 'var(--font-geist-sans)' }}>
              JAPAN CHAMPIONSHIPS 2026 - FINAL
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Time / Info */}
          <div className="flex items-center gap-2 text-yellow-400 font-mono font-bold text-lg drop-shadow-md">
            <span>⏱ 5:24</span>
          </div>

          {/* Visual Mode Toggle */}
          <button
            onClick={() => setShowVisualMode(!showVisualMode)}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors border text-xs font-bold",
              showVisualMode ? "bg-yellow-500 border-yellow-400 text-black shadow-[0_0_10px_orange]" : "bg-black border-white/20 text-gray-300 hover:bg-white/10"
            )}
          >
            {showVisualMode ? <ChartBar className="w-4 h-4" /> : <Presentation className="w-4 h-4" />}
            {showVisualMode ? "データ画面に戻る" : "解説図解モード"}
          </button>

          <div className="flex items-center gap-2 text-xs text-gray-500">
            <input
              type="text"
              value={showdownUrl}
              onChange={(e) => setShowdownUrl(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 w-32 focus:border-blue-500 outline-none"
            />
          </div>
        </div>
      </header>

      {/* Main Broadcasting Layout */}
      <div className="flex-1 relative z-10 flex flex-col min-h-0">

        {/* Upper Stage: Players + Center Screen */}
        {/* Shrinking Factor: Higher flex on bottom means less space here */}
        <div className="flex-1 flex min-h-0 relative items-center">
          <div className="w-[140px] h-full relative p-2 flex flex-col justify-center bg-gradient-to-r from-black via-black/50 to-transparent z-20">
            <PlayerPanel
              name={p1.name}
              rating={p1.rating}
              isSelf={true}
              pokemon={p1.pokemon}
            />
          </div>

          <div className="flex-1 h-full py-2 relative flex items-center justify-center">
            {/* Aspect Video constrains height, so shrinking container naturally shrinks iframe */}
            <div className="w-full max-h-full max-w-[1000px] aspect-video shadow-2xl rounded-xl overflow-hidden border border-gray-800 relative">
              <ShowdownFrame roomUrl={showdownUrl} />

              {showReasoning && (
                <div className="absolute top-4 right-4 w-80 h-[300px] z-30">
                  <ReasoningView
                    thoughtProcess={`■ 局面分析 (Turn 5) \n相手の黒バドレックスはゴーストテラスタルを切る可能性が高い。\n...`}
                    turn={5}
                    className="shadow-2xl border-white/20 bg-black/90 backdrop-blur-xl"
                  />
                </div>
              )}
            </div>
          </div>

          <div className="w-[140px] h-full relative p-2 flex flex-col justify-center bg-gradient-to-l from-black via-black/50 to-transparent z-20">
            <PlayerPanel
              name={p2.name}
              rating={p2.rating}
              isSelf={false}
              pokemon={p2.pokemon}
            />
          </div>
        </div>

        {/* Lower Stage: WinRate & Candidates OR Visual Diagram */}
        {/* Increased Height to 340px (from 220px) to prioritize explanation */}
        <div className="h-[340px] shrink-0 bg-gradient-to-b from-black/90 to-black border-t-2 border-white/10 relative z-30 flex flex-col overflow-hidden shadow-[0_-5px_20px_rgba(0,0,0,0.5)]">

          {showVisualMode ? (
            <VisualReasoningView
              p1Pokemon={p1.pokemon}
              p2Pokemon={p2.pokemon}
              onClose={() => setShowVisualMode(false)}
            />
          ) : (
            <>
              <div className="w-full h-12 relative -mt-6 z-40 px-8 max-w-6xl mx-auto group cursor-pointer" onClick={() => setShowVisualMode(true)}>
                <WinRateBar p1WinRate={WINRATE_MOCK} />
                <div className="absolute top-[-20px] left-1/2 -translate-x-1/2 bg-yellow-500 text-black text-[10px] font-bold px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                  👆 クリックで解説図解を表示
                </div>
              </div>

              <div className="flex-1 grid grid-cols-2 gap-8 px-8 py-4 max-w-6xl mx-auto w-full items-start min-h-0 overflow-y-auto">
                <div className="flex flex-col gap-2">
                  <div className="text-red-500 font-bold border-b border-red-500/30 pb-1 mb-1 text-sm flex justify-between">
                    <span>{p1.name} 予測手</span>
                  </div>
                  <BroadcastCandidateList candidates={mockCandidatesP1} color="red" />
                </div>

                <div className="flex flex-col gap-2">
                  <div className="text-blue-500 font-bold border-b border-blue-500/30 pb-1 mb-1 text-sm flex justify-between">
                    <span>{p2.name} 予測手</span>
                  </div>
                  <BroadcastCandidateList candidates={mockCandidatesP2} color="blue" />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
