export interface TrajectoryStep {
  step: number;
  reasoning: string;
  tool_call: {
    tool: string;
    args: Record<string, unknown>;
  };
}

export interface StepResult {
  step: number;
  reasoning: string;
  tool: string;
  args: Record<string, unknown>;
  divergence_score: number;
  flagged: boolean;
  explanation: string;
  rule_name?: string;
  severity?: string;
  error?: boolean;
}

export interface Session {
  id: number;
  source: string;
  log_path: string | null;
  started_at: string;
  completed_at: string | null;
  total_steps: number;
  flagged_count: number;
}
