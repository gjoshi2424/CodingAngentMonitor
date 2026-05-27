"use client";

export type Tab = "analysis" | "history";

interface TabNavProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  sessionCount?: number;
}

export default function TabNav({ activeTab, onTabChange, sessionCount }: TabNavProps) {
  const tabs: Tab[] = ["analysis", "history"];

  return (
    <div className="flex border-b border-gray-200 dark:border-gray-800 mb-6">
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onTabChange(tab)}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px capitalize transition-colors ${
            activeTab === tab
              ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
          }`}
        >
          {tab}
          {tab === "history" && sessionCount !== undefined && sessionCount > 0 && (
            <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-gray-800 text-xs text-gray-600 dark:text-gray-400">
              {sessionCount}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
