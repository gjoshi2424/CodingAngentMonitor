interface RunButtonProps {
  onClick: () => void;
  isAnalyzing: boolean;
}

export default function RunButton({ onClick, isAnalyzing }: RunButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={isAnalyzing}
      className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors cursor-pointer"
    >
      {isAnalyzing ? "Analyzing…" : "Run"}
    </button>
  );
}
