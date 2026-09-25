# CodeImpact — AI-Powered Code Change Impact Analysis Platform

CodeImpact is an intelligent developer platform that ingests full codebases, parses them with Tree-sitter AST grammars, constructs deep multi-relational knowledge graphs and FAISS semantic vector indexes, and orchestrates an AI Impact Agent to predict and visualize how code changes ripple through your software architecture before you merge.

---

## Key Features

- **Multi-Language Tree-sitter Ingestion**: Deep AST parsing for Python, TypeScript/JavaScript, Java, Go, and C/C++.
- **Hybrid Code Intelligence**:
  - **Knowledge Graph (NetworkX)**: Models files, classes, functions, API endpoints, tests, and variables connected by `CALLS`, `IMPORTS`, `CONTAINS`, `TESTS`, and `DEPENDS_ON` edges.
  - **Semantic RAG (FAISS + MiniLM)**: Dense vector retrieval with contextual code snippets.
- **Change Impact Propagation**:
  - Breadth-first impact path discovery across call graphs.
  - Risk scoring (High / Medium / Low) with blast radius calculations.
  - API endpoint impact detection and regression risk flags.
- **Test Impact Analysis**: Identifies tests covering affected code and produces prioritized test run recommendations.
- **AI-Powered Reasoning**: Explains change rationale, failure scenarios, and safety suggestions via OpenAI / Gemini / Ollama.
- **Multi-Source Verification Engine**: Cross-validates static AST evidence, call graphs, and vector similarity before finalizing reports.
- **Interactive D3.js Visualizer**: Force-directed graph explorer with zoom/pan, node filtering, path highlight, and node inspector.

---

## Architecture Overview

```
                          ┌──────────────────────────┐
                          │     React Dashboard      │
                          │   Vite + D3.js + Framer  │
                          └─────────────┬────────────┘
                                        │ (REST / WS)
                                        ▼
                          ┌──────────────────────────┐
                          │     FastAPI Backend      │
                          └──────┬────────────┬──────┘
                                 │            │
             ┌───────────────────┴──┐      ┌──┴───────────────────┐
             ▼                      ▼      ▼                      ▼
┌──────────────────────────┐ ┌──────────┐ ┌───────────────────┐ ┌─────────────────┐
│ Repository Ingestion     │ │  Tree-   │ │  Knowledge Graph  │ │  FAISS Vector   │
│ (Git Clone / Local Scan) │ │  sitter  │ │    (NetworkX)     │ │ Store + RAG     │
└──────────────────────────┘ └──────────┘ └───────────────────┘ └─────────────────┘
                                   │               │                     │
                                   └───────┬───────┴─────────────────────┘
                                           │
                                           ▼
                             ┌──────────────────────────┐
                             │    AI Impact Agent       │
                             │  • Intent Understanding  │
                             │  • Multi-Tool Evidence   │
                             │  • Impact Propagation    │
                             │  • Test Recommendations  │
                             │  • Cross-Verification    │
                             │  • LLM Rationale Report  │
                             └──────────────────────────┘
```

---

## Quick Start Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Setup

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Run FastAPI backend
uvicorn app.main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:5173`.

---

## Analysis Workflow

1. **Connect Repository**: Point to a local path or Git clone URL. The ingestion pipeline indexes all files, runs Tree-sitter parsing, constructs the knowledge graph, and indexes embeddings in FAISS.
2. **Submit Change Request**: Provide a natural language description (e.g., *"refactor the authenticate method in AuthService to use JWT tokens"*).
3. **Inspect 12-Step Agent Pipeline**: Watch the agent query the graph, pull RAG context, trace call paths, calculate risk scores, and formulate test recommendations.
4. **Explore the Graph Explorer**: Use the interactive D3.js force-directed canvas to visually explore nodes and dependencies.

---

## License

MIT
