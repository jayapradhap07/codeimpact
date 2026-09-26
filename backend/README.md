# CodeImpact Backend

FastAPI-powered intelligence engine for code change impact analysis.

## Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point with CORS & routes
│   ├── config.py            # Pydantic BaseSettings configuration
│   ├── api/
│   │   ├── deps.py          # Dependency injection (DB, repositories, graph)
│   │   └── routes/
│   │       ├── repositories.py  # Ingestion & repo management endpoints
│   │       ├── analysis.py      # Impact analysis execution & history
│   │       └── search.py        # Semantic & symbol code search
│   ├── core/
│   │   ├── ingestion.py     # Git clone & file traversal
│   │   ├── parser.py        # Multi-language Tree-sitter & AST parser
│   │   ├── chunker.py       # Function/class code chunking
│   │   ├── dependency.py    # Import & call graph analyzer
│   │   └── embeddings.py    # SentenceTransformers vectorizer
│   ├── graph/
│   │   └── knowledge_graph.py  # NetworkX DiGraph wrapper
│   ├── search/
│   │   ├── vector_store.py  # FAISS dense vector index
│   │   ├── code_search.py   # Regex & symbol name search
│   │   └── rag.py           # Retrieval-Augmented Generation engine
│   ├── agent/
│   │   ├── impact_agent.py  # 12-step agent orchestration pipeline
│   │   ├── impact_engine.py # BFS propagation, blast radius & risk scoring
│   │   ├── test_impact.py   # Test suite discovery & coverage recommendation
│   │   └── verification.py  # Cross-evidence verification engine
│   ├── llm/
│   │   ├── provider.py      # OpenAI, Gemini & Ollama adapters
│   │   └── prompts.py       # Structured reasoning prompts
│   ├── models/
│   │   └── schemas.py       # Pydantic data schemas for request/response
│   └── db/
│       ├── database.py      # SQLite / SQLAlchemy async engine
│       └── models.py        # Database ORM models
└── tests/                   # Pytest test suite
```

## Environment Configuration

Copy `.env.example` to `.env` and set:

```env
# Server & App
APP_NAME=AI Code Explanation & Debugger Bot
PORT=8000
APP_ENV=development
DEBUG=false

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/coderag.db

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:3b
OLLAMA_TIMEOUT_SECONDS=240.0

# Storage
CHROMA_PERSIST_DIR=./data/chroma_data
REPO_STORAGE_PATH=./data/repos
```

## Running Tests

```bash
pytest tests/ -v
```
