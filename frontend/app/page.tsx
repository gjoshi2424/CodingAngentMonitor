"use client";

import { useState } from "react";
import { Tab } from "./components/TabNav";
import AnalysisPage from "./tabs/analysis";
import HistoryPage from "./tabs/history";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("analysis");

  return activeTab === "analysis" ? (
    <AnalysisPage activeTab={activeTab} onTabChange={setActiveTab} />
  ) : (
    <HistoryPage activeTab={activeTab} onTabChange={setActiveTab} />
  );
}
