import { StepResult } from "./types";

interface StepCardProps {
  result: StepResult;
}

function stripMarkdown(text: string): string {
  return text
    .replace(/`([^`]*)`/g, "$1")        // inline code spans
    .replace(/\*\*([^*]+)\*\*/g, "$1")  // bold
    .replace(/\*([^*]+)\*/g, "$1");     // italic
}

export default function StepCard({ result }: StepCardProps) {
  return (
    <div
      className={`rounded-xl border p-5 ${
        result.error
          ? "border-yellow-400 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-950/30"
          : result.flagged
          ? "border-red-400 dark:border-red-700 bg-red-50 dark:bg-red-950/30"
          : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
      }`}
    >
      {/* Card header */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm font-semibold text-gray-500 dark:text-gray-400">
          Step {result.step}
        </span>
        {result.error ? (
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-yellow-700 text-white">
            JUDGE ERROR
          </span>
        ) : result.flagged ? (
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-600 text-white">
            {result.severity === "high" ? "RULE · HIGH" : "FLAGGED"}
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-700 text-white">
            OK
          </span>
        )}
        {result.severity === "medium" && (
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-orange-500 text-white">
            RULE · MED
          </span>
        )}
        <span
          className={`ml-auto text-right text-sm font-mono font-semibold ${
            result.divergence_score >= 0.7
              ? "text-red-600 dark:text-red-400"
              : result.divergence_score >= 0.4
                ? "text-yellow-600 dark:text-yellow-400"
                : "text-emerald-600 dark:text-emerald-400"
          }`}
          title="Divergence score: how much the agent's action diverges from its stated reasoning (0.0 = fully aligned, 1.0 = severe mismatch)"
        >
          divergence score: {result.divergence_score.toFixed(2)}
          <span className="block text-gray-400 dark:text-gray-500 font-normal text-xs font-sans">
            reasoning vs action
          </span>
        </span>
      </div>

      {/* Card body */}
      <div className="space-y-3 text-sm">
        <div>
          <span className="text-gray-500 dark:text-gray-500 text-xs uppercase tracking-wider">
            Reasoning
          </span>
          <p className="mt-1 text-gray-700 dark:text-gray-200">{stripMarkdown(result.reasoning)}</p>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-500 text-xs uppercase tracking-wider">
            Action
          </span>
          <p className="mt-1 font-mono text-indigo-600 dark:text-indigo-300 text-xs break-all">
            {result.tool}({JSON.stringify(result.args)})
          </p>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-500 text-xs uppercase tracking-wider">
            Judge
          </span>
          <p className="mt-1 text-gray-600 dark:text-gray-300">{stripMarkdown(result.explanation)}</p>
        </div>
      </div>
    </div>
  );
}
