"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { StepResult } from "../types";
import Button from "../components/Button";
import Loader from "../components/Loader";
import StepCard from "../components/StepCard";
import ThemeToggle from "../components/ThemeToggle";
import TabNav, { Tab } from "../components/TabNav";
import { getSessions, sseUrl, ROUTES } from "../api";

interface AnalysisPageProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export default function AnalysisPage({ activeTab, onTabChange }: AnalysisPageProps) {
  const [results, setResults] = useState<StepResult[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [analysisMode, setAnalysisMode] = useState<"mock" | "live" | "watch">("mock");
  const [isWatching, setIsWatching] = useState(false);
  const watchEsRef = useRef<EventSource | null>(null);
  const watchBatchActive = useRef(false);

  const [sessionCount, setSessionCount] = useState<number>(0);

  const fetchSessionCount = useCallback(async () => {
    try {
      const sessions = await getSessions();
      setSessionCount(sessions.length);
    } catch {
      // backend may not be running yet
    }
  }, []);

  useEffect(() => {
    fetchSessionCount();
  }, [fetchSessionCount]);

  function clearResults() {
    setResults([]);
    setIsDone(false);
    setErrorMessage(null);
  }

  function runAnalysis(mode: "mock" | "live") {
    setResults([]);
    setIsDone(false);
    setIsAnalyzing(true);
    setErrorMessage(null);
    setAnalysisMode(mode);

    const endpoint = mode === "live" ? ROUTES.analyzeLive : ROUTES.analyzeMock;
    const es = new EventSource(sseUrl(endpoint));

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.done) {
        setIsDone(true);
        setIsAnalyzing(false);
        es.close();
        fetchSessionCount();
        return;
      }
      setResults((prev) => [...prev, data as StepResult]);
    };

    es.onerror = () => {
      setIsAnalyzing(false);
      setErrorMessage("Connection to the backend failed. Is the server running?");
      es.close();
    };
  }

  function startWatch() {
    if (watchEsRef.current) return;
    setResults([]);
    setIsDone(false);
    setIsAnalyzing(false);
    setErrorMessage(null);
    setAnalysisMode("watch");
    setIsWatching(true);
    watchBatchActive.current = false;

    const es = new EventSource(sseUrl(ROUTES.watch));
    watchEsRef.current = es;

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.done) {
        watchBatchActive.current = false;
        setIsAnalyzing(false);
        setIsDone(true);
        fetchSessionCount();
        return;
      }
      if (!watchBatchActive.current) {
        watchBatchActive.current = true;
        setIsDone(false);
        setIsAnalyzing(true);
      }
      setResults((prev) => [...prev, data as StepResult]);
    };

    es.onerror = () => {
      setErrorMessage("Watch connection lost. Is the backend still running?");
      stopWatch();
    };
  }

  function stopWatch() {
    watchEsRef.current?.close();
    watchEsRef.current = null;
    setIsWatching(false);
    setIsAnalyzing(false);
  }

  const showClear = results.length > 0 && (isDone || (!isWatching && !isAnalyzing));

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-tight">Agent Monitor</h1>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button
              onClick={() => runAnalysis("mock")}
              disabled={isAnalyzing || isWatching}
              className="bg-indigo-600 hover:bg-indigo-500 text-white"
            >
              {isAnalyzing && analysisMode === "mock" ? "Analyzing…" : "Run Example"}
            </Button>
            <Button
              onClick={() => runAnalysis("live")}
              disabled={isAnalyzing || isWatching}
              className="border border-cyan-500/60 bg-cyan-500/10 text-cyan-700 dark:text-cyan-200 hover:bg-cyan-500/20"
            >
              {isAnalyzing && analysisMode === "live" ? "Live…" : "Run Latest"}
            </Button>
            {isWatching ? (
              <Button
                onClick={stopWatch}
                className="border border-rose-500/60 bg-rose-500/10 text-rose-700 dark:text-rose-300 hover:bg-rose-500/20"
              >
                Stop Watching
              </Button>
            ) : (
              <Button
                onClick={startWatch}
                disabled={isAnalyzing}
                className="border border-violet-500/60 bg-violet-500/10 text-violet-700 dark:text-violet-200 hover:bg-violet-500/20"
              >
                Watch
              </Button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <TabNav activeTab={activeTab} onTabChange={onTabChange} sessionCount={sessionCount} />

        {isAnalyzing && <Loader />}

        {errorMessage && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/40 border border-yellow-300 dark:border-yellow-700 text-yellow-800 dark:text-yellow-300 text-sm font-medium">
            ⚠ {errorMessage}
          </div>
        )}

        {isWatching && !isAnalyzing && !isDone && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-violet-50 dark:bg-violet-900/40 border border-violet-300 dark:border-violet-700 text-violet-800 dark:text-violet-300 text-sm font-medium">
            Watching ~/.claude/projects/ for changes…
          </div>
        )}

        {isDone && (
          <div className="mb-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/40 border border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-300 text-sm font-medium">
            <span>
              ✓{" "}
              {analysisMode === "live"
                ? "Live"
                : analysisMode === "watch"
                ? "Watch"
                : "Mock"}{" "}
              analysis complete
              {isWatching && " — waiting for next change"}
            </span>
            {showClear && (
              <button
                onClick={clearResults}
                className="ml-auto px-3 py-1 rounded-md text-xs font-semibold bg-emerald-100 dark:bg-emerald-900 hover:bg-emerald-200 dark:hover:bg-emerald-800 text-emerald-700 dark:text-emerald-300 transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        )}

        {/* Watch stopped with results */}
        {!isWatching && !isAnalyzing && !isDone && results.length > 0 && (
          <div className="mb-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-gray-100 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 text-sm">
            <span>Watch stopped.</span>
            <button
              onClick={clearResults}
              className="ml-auto px-3 py-1 rounded-md text-xs font-semibold bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition-colors"
            >
              Clear
            </button>
          </div>
        )}

        <div className="space-y-4">
          {results.map((result, index) => (
            <StepCard key={`${analysisMode}-${result.step}-${index}`} result={result} />
          ))}
        </div>

        {results.length === 0 && !isAnalyzing && !errorMessage && !isWatching && (
          <p className="text-sm text-gray-400 dark:text-gray-600 italic">
            Run an analysis or start watching to see results.
          </p>
        )}
      </div>
    </main>
  );
}
