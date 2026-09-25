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
# Server
PORT=8000
ENVIRONMENT=development

# Storage
DB_PATH=data/codeimpact.db
VECTOR_STORAGE_DIR=data/vectors
REPOS_STORAGE_DIR=data/repositories

# AI / LLM Configuration
LLM_PROVIDER=openai # or gemini / ollama
OPENAI_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
OLLAMA_BASE_URL=http://localhost:11434
```

## Running Tests

```bash
pytest tests/ -v
```
