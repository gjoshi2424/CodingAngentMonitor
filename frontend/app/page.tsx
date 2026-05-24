"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { StepResult, Session } from "./components/types";
import Button from "./components/Button";
import Loader from "./components/Loader";
import StepCard from "./components/StepCard";

const API = "http://localhost:8000";

export default function Home() {
  const [results, setResults] = useState<StepResult[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"mock" | "live" | "watch">("mock");
  const [isWatching, setIsWatching] = useState(false);
  const watchEsRef = useRef<EventSource | null>(null);
  const watchBatchActive = useRef(false);

  // Session history state
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<{ session: Session; steps: StepResult[] } | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
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
        setHistoryOpen(true);
      }
    } finally {
      setHistoryLoading(false);
    }
  }

  function runAnalysis(mode: "mock" | "live") {
    setResults([]);
    setIsDone(false);
    setIsAnalyzing(true);
    setAnalysisMode(mode);
    setSelectedSession(null);

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
    setSelectedSession(null);
    watchBatchActive.current = false;

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

    es.onerror = () => stopWatch();
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

        {isWatching && !isAnalyzing && !isDone && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-violet-900/40 border border-violet-700 text-violet-300 text-sm font-medium">
            Watching ~/.claude/projects/ for changes…
          </div>
        )}

        {isDone && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-emerald-900/40 border border-emerald-700 text-emerald-300 text-sm font-medium">
            ✓ {analysisMode === "live" ? "Live" : analysisMode === "watch" ? "Watch" : "Mock"} analysis complete
            {isWatching && " — waiting for next change"}
          </div>
        )}

        <div className="space-y-4">
          {results.map((result, index) => (
            <StepCard key={`${analysisMode}-${result.step}-${index}`} result={result} />
          ))}
        </div>

        {/* Past Sessions */}
        <div className="mt-10">
          <button
            onClick={() => {
              setHistoryOpen((o) => !o);
              if (!historyOpen) fetchSessions();
            }}
            className="flex items-center gap-2 text-sm font-semibold text-gray-400 hover:text-gray-200 transition-colors mb-4"
          >
            <span className={`transition-transform ${historyOpen ? "rotate-90" : ""}`}>▶</span>
            Past Sessions
            {sessions.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded bg-gray-800 text-xs text-gray-400">
                {sessions.length}
              </span>
            )}
          </button>

          {historyOpen && (
            <div className="space-y-2">
              {sessions.length === 0 && (
                <p className="text-sm text-gray-600 italic">No sessions saved yet.</p>
              )}
              {sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => openSession(s.id)}
                  className="w-full text-left rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 hover:border-gray-500 hover:bg-gray-800 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-500">#{s.id}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 font-medium capitalize">
                      {s.source}
                    </span>
                    {s.flagged_count > 0 && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-red-900/60 text-red-300 font-medium">
                        {s.flagged_count} flagged
                      </span>
                    )}
                    <span className="ml-auto text-xs text-gray-500">
                      {s.total_steps} steps · {formatDate(s.started_at)}
                    </span>
                  </div>
                  {s.log_path && (
                    <p className="mt-1 text-xs text-gray-600 font-mono truncate">{s.log_path}</p>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Session detail overlay */}
        {selectedSession && (
          <div className="fixed inset-0 z-50 bg-gray-950/90 overflow-y-auto p-8">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center gap-4 mb-6">
                <button
                  onClick={() => setSelectedSession(null)}
                  className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
                >
                  ← Back
                </button>
                <h2 className="text-xl font-bold">
                  Session #{selectedSession.session.id}
                  <span className="ml-3 text-sm font-normal text-gray-400 capitalize">
                    {selectedSession.session.source}
                  </span>
                </h2>
                <span className="ml-auto text-sm text-gray-500">
                  {formatDate(selectedSession.session.started_at)}
                </span>
              </div>
              {selectedSession.session.log_path && (
                <p className="mb-4 text-xs text-gray-600 font-mono">{selectedSession.session.log_path}</p>
              )}
              <div className="space-y-4">
                {selectedSession.steps.map((step) => (
                  <StepCard key={step.step} result={step} />
                ))}
              </div>
            </div>
          </div>
        )}

        {historyLoading && (
          <div className="fixed inset-0 z-40 flex items-center justify-center bg-gray-950/60">
            <Loader />
          </div>
        )}
      </div>
    </main>
  );
}
