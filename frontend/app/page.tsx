"use client";

import { useState, useRef } from "react";
import { StepResult } from "./components/types";
import Button from "./components/Button";
import Loader from "./components/Loader";
import StepCard from "./components/StepCard";

export default function Home() {
  const [results, setResults] = useState<StepResult[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"mock" | "live" | "watch">("mock");
  const [isWatching, setIsWatching] = useState(false);
  const watchEsRef = useRef<EventSource | null>(null);
  const watchBatchActive = useRef(false);

  function runAnalysis(mode: "mock" | "live") {
    setResults([]);
    setIsDone(false);
    setIsAnalyzing(true);
    setAnalysisMode(mode);

    const endpoint =
      mode === "live" ? "/analyze/live" : "/analyze/mock";
    const es = new EventSource(`http://localhost:8000${endpoint}`);

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.done) {
        setIsDone(true);
        setIsAnalyzing(false);
        es.close();
        return;
      }
      setResults((prev) => [...prev, data as StepResult]);
    };

    es.onerror = () => {
      setIsAnalyzing(false);
      es.close();
    };
  }

  function startWatch() {
    if (watchEsRef.current) return;
    setResults([]);
    setIsDone(false);
    setIsAnalyzing(false);
    setAnalysisMode("watch");
    setIsWatching(true);
    watchBatchActive.current = false;

    const es = new EventSource("http://localhost:8000/watch");
    watchEsRef.current = es;

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.done) {
        watchBatchActive.current = false;
        setIsAnalyzing(false);
        setIsDone(true);
        return;
      }
      if (!watchBatchActive.current) {
        watchBatchActive.current = true;
        setIsDone(false);
        setIsAnalyzing(true);
      }
      setResults((prev) => [...prev, data as StepResult]);
    };

    es.onerror = () => stopWatch();
  }

  function stopWatch() {
    watchEsRef.current?.close();
    watchEsRef.current = null;
    setIsWatching(false);
    setIsAnalyzing(false);
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold tracking-tight">Agent Monitor</h1>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => runAnalysis("mock")}
              disabled={isAnalyzing || isWatching}
              className="bg-indigo-600 hover:bg-indigo-500"
            >
              {isAnalyzing && analysisMode === "mock" ? "Analyzing…" : "Run Example"}
            </Button>
            <Button
              onClick={() => runAnalysis("live")}
              disabled={isAnalyzing || isWatching}
              className="border border-cyan-500/60 bg-cyan-500/10 text-cyan-200 hover:bg-cyan-500/20"
            >
              {isAnalyzing && analysisMode === "live" ? "Live…" : "Run Latest"}
            </Button>
            {isWatching ? (
              <Button
                onClick={stopWatch}
                className="border border-rose-500/60 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20"
              >
                Stop Watching
              </Button>
            ) : (
              <Button
                onClick={startWatch}
                disabled={isAnalyzing}
                className="border border-violet-500/60 bg-violet-500/10 text-violet-200 hover:bg-violet-500/20"
              >
                Watch
              </Button>
            )}
          </div>
        </div>

        {/* Loading state */}
        {isAnalyzing && <Loader />}

        {/* Watching idle state */}
        {isWatching && !isAnalyzing && !isDone && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-violet-900/40 border border-violet-700 text-violet-300 text-sm font-medium">
            Watching ~/.claude/projects/ for changes…
          </div>
        )}

        {/* Done state */}
        {isDone && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-emerald-900/40 border border-emerald-700 text-emerald-300 text-sm font-medium">
            ✓ {analysisMode === "live" ? "Live" : analysisMode === "watch" ? "Watch" : "Mock"} analysis complete
            {isWatching && " — waiting for next change"}
          </div>
        )}

        {/* Step cards */}
        <div className="space-y-4">
          {results.map((result, index) => (
            <StepCard key={`${analysisMode}-${result.step}-${index}`} result={result} />
          ))}
        </div>
      </div>
    </main>
  );
}
