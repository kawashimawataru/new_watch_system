"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { ShowdownFrame } from "@/components/ShowdownFrame";
import { PlayerPanel } from "@/components/PlayerPanel";
import { WinRateBar } from "@/components/WinRateBar";
import { BroadcastCandidateList, CandidateMove } from "@/components/BroadcastCandidateList";
import { ReasoningView } from "@/components/ReasoningView";
import { VisualReasoningView } from "@/components/VisualReasoningView";
import { EffectOverlay, EffectType } from "@/components/EffectOverlay";
import { DebugPad } from "@/components/DebugPad";
import { useGameState, CandidateMove as BackendCandidate } from "@/hooks/useGameState";
import { cn } from "@/lib/utils";
import { BrainCircuit, Presentation, ChartBar, Wifi, WifiOff } from "lucide-react";

export default function SpectatorPage() {
  const { isConnected, gameState, winRateHistory, battleType, candidates, explanation } = useGameState();
  const [showdownUrl, setShowdownUrl] = useState("http://localhost:8002/");
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

  // Default/Mock data (Japanese) - used when disconnected
  const defaultP1 = { name: "Player 1", rating: 1500, pokemon: ["ポケモン1", "ポケモン2", "ポケモン3", "ポケモン4"] };
  const defaultP2 = { name: "Opponent", rating: 1500, pokemon: ["ポケモンA", "ポケモンB", "ポケモンC", "ポケモンD"] };

  // Use live data if available, else fallback to mock
  const p1 = gameState?.p1?.name ? gameState.p1 : defaultP1;
  const p2 = gameState?.p2?.name ? gameState.p2 : defaultP2;
  const currentWinRate = gameState?.winRate ?? 0.5;
  const currentTurn = gameState?.turn ?? 0;

  // Convert backend candidates to frontend format
  const convertCandidates = (backendCandidates: BackendCandidate[] | undefined): CandidateMove[] => {
    if (!backendCandidates || backendCandidates.length === 0) {
      return [];
    }
    return backendCandidates.map(c => ({
      move1: c.move1,
      target1: c.target1,
      type1: c.type1,
      move2: c.move2,
      target2: c.target2,
      type2: c.type2,
      score: c.score,
    }));
  };

  // Get candidates - live or mock
  const p1Candidates: CandidateMove[] = useMemo(() => {
    if (candidates?.p1 && candidates.p1.length > 0) {
      return convertCandidates(candidates.p1);
    }
    // Mock data fallback
    return [
      {
        move1: "ドレインパンチ", target1: "バドレックス", type1: "attack",
        move2: "だいちのちから", target2: "ウーラオス", type2: "attack", score: 42
      },
      {
        move1: "ねこだまし", target1: "ウーラオス", type1: "protect",
        move2: "テラクラスター", target2: "バドレックス", type2: "attack", score: 28
      },
      {
        move1: "交代 -> モロバレル", target1: "", type1: "switch",
        move2: "まもる", target2: "", type2: "protect", score: 15
      },
    ];
  }, [candidates, mockRefreshKey]);

  const p2Candidates: CandidateMove[] = useMemo(() => {
    if (candidates?.p2 && candidates.p2.length > 0) {
      return convertCandidates(candidates.p2);
    }
    // Mock data fallback
    return [
      {
        move1: "アストラルビット", target1: "全体", type1: "attack",
        move2: "インファイト", target2: "テラパゴス", type2: "attack", score: 65
      },
      {
        move1: "まもる", target1: "", type1: "protect",
        move2: "すいりゅうれんだ", target2: "ガオガエン", type2: "attack", score: 20
      },
      {
        move1: "アストラルビット", target1: "全体", type1: "attack",
        move2: "守る", target2: "", type2: "protect", score: 10
      },
    ];
  }, [candidates, mockRefreshKey]);

  // Explanation text
  const playerStrategy = explanation?.playerStrategy ?? "データ受信待ち...";
  const opponentThreat = explanation?.opponentThreat ?? "";
  const currentSituation = explanation?.currentSituation;
  const topCandidateReason = explanation?.topCandidateReason;
  const riskAnalysis = explanation?.riskAnalysis;

  const handleUpdateData = () => {
    setMockRefreshKey(prev => prev + 1);
  };

  // Debug: Layout measurement refs
  const winRateBarContainerRef = useRef<HTMLDivElement>(null);
  const candidateListContainerRef = useRef<HTMLDivElement>(null);
  const p1CandidateListRef = useRef<HTMLDivElement>(null);

  // Debug: Measure layout after render
  useEffect(() => {
    const measureLayout = () => {
      // #region agent log
      if (winRateBarContainerRef.current) {
        const rect = winRateBarContainerRef.current.getBoundingClientRect();
        const styles = window.getComputedStyle(winRateBarContainerRef.current);
        fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'page.tsx:useEffect',message:'WinRateBar container dimensions',data:{height:rect.height,top:rect.top,bottom:rect.bottom,width:rect.width,computedHeight:styles.height},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch((e)=>console.error('Debug log error:',e));
      }
      if (candidateListContainerRef.current) {
        const rect = candidateListContainerRef.current.getBoundingClientRect();
        const styles = window.getComputedStyle(candidateListContainerRef.current);
        fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'page.tsx:useEffect',message:'Candidate list container dimensions',data:{height:rect.height,top:rect.top,bottom:rect.bottom,width:rect.width,paddingTop:styles.paddingTop},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch((e)=>console.error('Debug log error:',e));
      }
      if (p1CandidateListRef.current) {
        const rect = p1CandidateListRef.current.getBoundingClientRect();
        fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'page.tsx:useEffect',message:'P1 candidate list position',data:{top:rect.top,bottom:rect.bottom,height:rect.height},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch((e)=>console.error('Debug log error:',e));
      }
      // Check for overlap
      if (winRateBarContainerRef.current && candidateListContainerRef.current) {
        const barRect = winRateBarContainerRef.current.getBoundingClientRect();
        const listRect = candidateListContainerRef.current.getBoundingClientRect();
        const overlap = barRect.bottom > listRect.top;
        fetch('http://127.0.0.1:7242/ingest/3375475e-c3d2-4387-93c1-d0dfa2e31d70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'page.tsx:useEffect',message:'Overlap detection',data:{barBottom:barRect.bottom,listTop:listRect.top,overlap,gap:listRect.top-barRect.bottom},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch((e)=>console.error('Debug log error:',e));
      }
      // #endregion
    };

    // Measure after initial render and on resize
    const timeoutId = setTimeout(measureLayout, 100);
    window.addEventListener('resize', measureLayout);
    
    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('resize', measureLayout);
    };
  }, [currentWinRate, p1Candidates, showVisualMode]);

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
            {/* Connection Status */}
            <div className={cn(
              "px-2 py-0.5 text-white text-[10px] font-bold tracking-widest uppercase rounded-sm flex items-center gap-1",
              isConnected ? "bg-green-600" : "bg-red-600 animate-pulse"
            )}>
              {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {isConnected ? "LIVE" : "OFFLINE"}
            </div>
            <span className="text-sm font-bold tracking-wider text-gray-200" style={{ fontFamily: 'var(--font-geist-sans)' }}>
              {isConnected ? `Turn ${currentTurn}` : "接続待機中..."}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
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
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 w-40 focus:border-blue-500 outline-none"
              placeholder="Showdown URL"
            />
          </div>
        </div>
      </header>

      {/* Main Broadcasting Layout */}
      <div className="flex-1 relative z-10 flex flex-col min-h-0">

        {/* Upper Stage: Players + Center Screen */}
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
            <div className="w-full max-h-full max-w-[1000px] aspect-video shadow-2xl rounded-xl overflow-hidden border border-gray-800 relative">
              <ShowdownFrame roomUrl={showdownUrl} />

              {showReasoning && (
                <div className="absolute top-4 right-4 w-80 h-[300px] z-30">
                  <ReasoningView
                    thoughtProcess={playerStrategy}
                    currentSituation={currentSituation}
                    topCandidateReason={topCandidateReason}
                    riskAnalysis={riskAnalysis}
                    turn={currentTurn}
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
        <div className="h-[340px] shrink-0 bg-gradient-to-b from-black/90 to-black border-t-2 border-white/10 relative z-30 flex flex-col overflow-hidden shadow-[0_-5px_20px_rgba(0,0,0,0.5)]">

          {showVisualMode ? (
            <VisualReasoningView
              p1Pokemon={p1.pokemon}
              p2Pokemon={p2.pokemon}
              playerStrategy={playerStrategy}
              opponentThreat={opponentThreat}
              currentSituation={currentSituation}
              topCandidateReason={topCandidateReason}
              riskAnalysis={riskAnalysis}
              battleType={battleType}
              onClose={() => setShowVisualMode(false)}
            />
          ) : (
            <>
              {/* #region agent log */}
              <div 
                ref={winRateBarContainerRef}
                className="w-full h-12 relative z-40 px-8 max-w-6xl mx-auto group cursor-pointer" 
                onClick={() => setShowVisualMode(true)}
              >
                <WinRateBar p1WinRate={currentWinRate * 100} />
                <div className="absolute top-[-20px] left-1/2 -translate-x-1/2 bg-yellow-500 text-black text-[10px] font-bold px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                  👆 クリックで解説図解を表示
                </div>
              </div>
              {/* #endregion */}

              {/* #region agent log */}
              <div 
                ref={candidateListContainerRef}
                className="flex-1 grid grid-cols-2 gap-8 px-8 pt-8 pb-4 max-w-6xl mx-auto w-full items-start min-h-0 overflow-y-auto"
              >
                {/* #region agent log */}
                <div 
                  ref={p1CandidateListRef}
                  className="flex flex-col gap-2"
                >
                  <div className="text-red-500 font-bold border-b border-red-500/30 pb-1 mb-1 text-sm flex justify-between">
                    <span>{p1.name} 予測手</span>
                    <span className="text-[10px] text-gray-500">{isConnected ? "LIVE" : "MOCK"}</span>
                  </div>
                  <BroadcastCandidateList candidates={p1Candidates} color="red" battleType={battleType} />
                </div>
                {/* #endregion */}

                <div className="flex flex-col gap-2">
                  <div className="text-blue-500 font-bold border-b border-blue-500/30 pb-1 mb-1 text-sm flex justify-between">
                    <span>{p2.name} 予測手</span>
                    <span className="text-[10px] text-gray-500">{isConnected ? "LIVE" : "MOCK"}</span>
                  </div>
                  <BroadcastCandidateList candidates={p2Candidates} color="blue" battleType={battleType} />
                </div>
              </div>
              {/* #endregion */}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
