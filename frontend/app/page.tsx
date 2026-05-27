"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { StepResult, Session } from "./components/types";
import Button from "./components/Button";
import Loader from "./components/Loader";
import StepCard from "./components/StepCard";
import ThemeToggle from "./components/ThemeToggle";

const API = "http://localhost:8000";

type Tab = "analysis" | "history";

export default function Home() {
  const [results, setResults] = useState<StepResult[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [analysisMode, setAnalysisMode] = useState<"mock" | "live" | "watch">("mock");
  const [isWatching, setIsWatching] = useState(false);
  const watchEsRef = useRef<EventSource | null>(null);
  const watchBatchActive = useRef(false);

  const [activeTab, setActiveTab] = useState<Tab>("analysis");

  // Session history state
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<{ session: Session; steps: StepResult[] } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API}/sessions`);
      if (res.ok) setSessions(await res.json());
    } catch {
      // backend may not be running yet
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  async function openSession(id: number) {
    setHistoryLoading(true);
    try {
      const res = await fetch(`${API}/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedSession(data);
      }
    } finally {
      setHistoryLoading(false);
    }
  }

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
    setSelectedSession(null);
    setActiveTab("analysis");

    const endpoint = mode === "live" ? "/analyze/live" : "/analyze/mock";
    const es = new EventSource(`${API}${endpoint}`);

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.done) {
        setIsDone(true);
        setIsAnalyzing(false);
        es.close();
        fetchSessions();
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
    setSelectedSession(null);
    watchBatchActive.current = false;
    setActiveTab("analysis");

    const es = new EventSource(`${API}/watch`);
    watchEsRef.current = es;

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.done) {
        watchBatchActive.current = false;
        setIsAnalyzing(false);
        setIsDone(true);
        fetchSessions();
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

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString();
  }

  // Show clear when stopped watching with results, or after done
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
        <div className="flex border-b border-gray-200 dark:border-gray-800 mb-6">
          {(["analysis", "history"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                if (tab === "history") {
                  fetchSessions();
                  setSelectedSession(null);
                }
              }}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px capitalize transition-colors ${
                activeTab === tab
                  ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              }`}
            >
              {tab}
              {tab === "history" && sessions.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-gray-800 text-xs text-gray-600 dark:text-gray-400">
                  {sessions.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Analysis tab ── */}
        {activeTab === "analysis" && (
          <>
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
          </>
        )}

        {/* ── History tab ── */}
        {activeTab === "history" && (
          <>
            {historyLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader />
              </div>
            )}

            {!historyLoading && !selectedSession && (
              <div className="space-y-2">
                {sessions.length === 0 && (
                  <p className="text-sm text-gray-400 dark:text-gray-600 italic">
                    No sessions saved yet.
                  </p>
                )}
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => openSession(s.id)}
                    className="w-full text-left rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3 hover:border-gray-400 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-gray-400 dark:text-gray-500">
                        #{s.id}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 font-medium capitalize">
                        {s.source}
                      </span>
                      {s.flagged_count > 0 && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/60 text-red-700 dark:text-red-300 font-medium">
                          {s.flagged_count} flagged
                        </span>
                      )}
                      <span className="ml-auto text-xs text-gray-400 dark:text-gray-500">
                        {s.total_steps} steps · {formatDate(s.started_at)}
                      </span>
                    </div>
                    {s.log_path && (
                      <p className="mt-1 text-xs text-gray-400 dark:text-gray-600 font-mono truncate">
                        {s.log_path}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}

            {!historyLoading && selectedSession && (
              <div>
                <div className="flex items-center gap-4 mb-6">
                  <button
                    onClick={() => setSelectedSession(null)}
                    className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
                  >
                    ← Back
                  </button>
                  <h2 className="text-lg font-bold">
                    Session #{selectedSession.session.id}
                    <span className="ml-3 text-sm font-normal text-gray-500 dark:text-gray-400 capitalize">
                      {selectedSession.session.source}
                    </span>
                  </h2>
                  <span className="ml-auto text-sm text-gray-400 dark:text-gray-500">
                    {formatDate(selectedSession.session.started_at)}
                  </span>
                </div>
                {selectedSession.session.log_path && (
                  <p className="mb-4 text-xs text-gray-400 dark:text-gray-600 font-mono">
                    {selectedSession.session.log_path}
                  </p>
                )}
                <div className="space-y-4">
                  {selectedSession.steps.map((step) => (
                    <StepCard key={step.step} result={step} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}


