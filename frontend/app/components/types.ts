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
}
