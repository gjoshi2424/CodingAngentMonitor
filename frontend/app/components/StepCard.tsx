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
        result.flagged
          ? "border-red-700 bg-red-950/30"
          : "border-gray-700 bg-gray-900"
      }`}
    >
      {/* Card header */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm font-semibold text-gray-400">
          Step {result.step}
        </span>
        {result.flagged ? (
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-600 text-white">
            FLAGGED
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-700 text-white">
            OK
          </span>
        )}
        <span
          className={`ml-auto text-sm font-mono font-semibold ${
            result.divergence_score >= 0.7
              ? "text-red-400"
              : result.divergence_score >= 0.4
                ? "text-yellow-400"
                : "text-emerald-400"
          }`}
        >
          score {result.divergence_score.toFixed(2)}
        </span>
      </div>

      {/* Card body */}
      <div className="space-y-3 text-sm">
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider">
            Reasoning
          </span>
          <p className="mt-1 text-gray-200">{stripMarkdown(result.reasoning)}</p>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider">
            Action
          </span>
          <p className="mt-1 font-mono text-indigo-300 text-xs break-all">
            {result.tool}({JSON.stringify(result.args)})
          </p>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider">
            Judge
          </span>
          <p className="mt-1 text-gray-300">{stripMarkdown(result.explanation)}</p>
        </div>
      </div>
    </div>
  );
}
