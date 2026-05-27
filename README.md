# Coding Agent Monitor

Watches Claude Code session logs and flags suspicious behaviour in real time — mismatches between what the agent *says* it is doing and what it *actually* does (tool calls and arguments).

Each step is evaluated by a two-layer pipeline:
1. **Rule engine** — fast, deterministic checks (credential exfiltration, destructive commands, sensitive file access). High-severity hits skip the LLM entirely.
2. **LLM judge** — a local Ollama model scores the divergence between stated reasoning and the tool call, injecting any rule hints for medium-severity steps.

Results stream to the browser over SSE as each step is judged.

## Architecture

```mermaid
flowchart TD
    subgraph Sources["Input Sources"]
        A1["📁 Claude Code\nlog files (.jsonl)"]
        A2["🔄 LogWatcher\n(watchdog + debounce)"]
        A3["MOCK_TRAJECTORY\n(built-in fixture)"]
        A1 -->|file change event| A2
    end

    subgraph Parser["parser.py"]
        B["parse_jsonl_log()\nExtracts: reasoning · tool · args\nper assistant message block"]
    end

    A1 -->|/analyze/live| B
    A2 -->|/watch| B
    A3 -->|/analyze/mock| B

    subgraph Pipeline["Analysis Pipeline  ·  streaming.py + monitor.py"]
        direction TB
        B --> D["For each step"]

        D --> E{"rules.py\nRule Engine"}

        E -->|"severity = high\n(exfil / rm / sensitive key)"| F1["⛔ Auto-flag\ndivergence = 1.0\nskip LLM"]
        E -->|"severity = medium\n(inject hint)"| F2["🤖 Ollama LLM Judge\nllama3.2 via OpenAI API\nreturns divergence_score + flagged"]
        E -->|no rule hit| F2

        F1 --> G["Build payload"]
        F2 --> G
    end

    subgraph Outputs["Outputs"]
        G --> H1["💾 SQLite\n(aiosqlite, WAL mode)\nsessions + analysis_steps"]
        G --> H2["📡 SSE stream\ndata: {step, tool, score, flagged, …}"]
        G --> H3["🔔 Slack alert\n(high severity only,\ndedup 60 s window)"]
    end

    subgraph Frontend["Frontend  ·  Next.js"]
        H2 --> I["EventSource\n/analyze/mock · /analyze/live · /watch"]
        I --> J["StepCard\nper-step result + score + flag"]
        H1 --> K["Session History\n/sessions  /sessions/:id"]
    end
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /analyze/mock` | Stream analysis of the built-in mock trajectory |
| `GET /analyze/live` | Stream analysis of the most recent Claude session log |
| `GET /watch` | SSE stream — stays open and emits results as new log events arrive |


## Running

**Backend**
```bash
cd backend
uv run uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```