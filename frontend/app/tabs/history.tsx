"use client";

import { useState, useCallback, useEffect } from "react";
import { Session, StepResult } from "../types";
import Loader from "../components/Loader";
import StepCard from "../components/StepCard";
import ThemeToggle from "../components/ThemeToggle";
import TabNav, { Tab } from "../components/TabNav";
import { getSessions, getSession } from "../api";

interface HistoryPageProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export default function HistoryPage({ activeTab, onTabChange }: HistoryPageProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<{ session: Session; steps: StepResult[] } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchSessions = useCallback(async () => {
    try {
      setSessions(await getSessions());
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
      setSelectedSession(await getSession(id));
    } catch {
      // session load failed — leave selectedSession as-is
    } finally {
      setHistoryLoading(false);
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString();
  }

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-tight">Agent Monitor</h1>
          <ThemeToggle />
        </div>

        {/* Tabs */}
        <TabNav activeTab={activeTab} onTabChange={onTabChange} sessionCount={sessions.length} />

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
      </div>
    </main>
  );
}
