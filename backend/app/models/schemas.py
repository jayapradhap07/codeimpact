"""Pydantic schemas for API request/response models."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Repository schemas
# ──────────────────────────────────────────────

class RepoConnectRequest(BaseModel):
    """Request to connect a repository."""
    url: Optional[str] = Field(None, description="Git clone URL")
    local_path: Optional[str] = Field(None, description="Local filesystem path")
    name: Optional[str] = Field(None, description="Display name (auto-detected if omitted)")


class RepoStatusResponse(BaseModel):
    """Repository status response."""
    id: int
    name: str
    url: Optional[str]
    local_path: str
    status: str
    languages: Optional[Dict[str, int]]
    file_count: int
    function_count: int
    class_count: int
    total_lines: int
    error_message: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class RepoListResponse(BaseModel):
    """List of repositories."""
    repositories: List[RepoStatusResponse]
    total: int


# ──────────────────────────────────────────────
# Code element schemas
# ──────────────────────────────────────────────

class CodeLocation(BaseModel):
    """Location of a code element."""
    file_path: str
    start_line: int
    end_line: int
    language: str = ""


class FunctionInfo(BaseModel):
    """Parsed function information."""
    name: str
    qualified_name: str = ""
    parameters: List[str] = []
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    location: CodeLocation
    is_method: bool = False
    class_name: Optional[str] = None
    decorators: List[str] = []


class ClassInfo(BaseModel):
    """Parsed class information."""
    name: str
    qualified_name: str = ""
    bases: List[str] = []
    methods: List[FunctionInfo] = []
    attributes: List[str] = []
    docstring: Optional[str] = None
    location: CodeLocation
    decorators: List[str] = []


class ImportInfo(BaseModel):
    """Parsed import information."""
    module: str
    names: List[str] = []
    alias: Optional[str] = None
    is_from_import: bool = False
    location: CodeLocation


class ParsedFile(BaseModel):
    """Result of parsing a single source file."""
    file_path: str
    language: str
    functions: List[FunctionInfo] = []
    classes: List[ClassInfo] = []
    imports: List[ImportInfo] = []
    variables: List[str] = []
    line_count: int = 0
    raw_content: str = ""


# ──────────────────────────────────────────────
# Code chunk schemas
# ──────────────────────────────────────────────

class ChunkType(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    BLOCK = "block"
    MODULE = "module"


class CodeChunk(BaseModel):
    """A semantic chunk of code for embedding."""
    id: str = ""
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: ChunkType
    name: str
    language: str
    qualified_name: str = ""
    metadata: Dict[str, Any] = {}


# ──────────────────────────────────────────────
# Dependency schemas
# ──────────────────────────────────────────────

class DependencyType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    INHERITS = "inherits"
    CONTAINS = "contains"
    TESTS = "tests"


class Dependency(BaseModel):
    """A dependency relationship between two code elements."""
    source: str  # qualified name or file path
    target: str  # qualified name or file path
    dep_type: DependencyType
    source_location: Optional[CodeLocation] = None
    metadata: Dict[str, Any] = {}


# ──────────────────────────────────────────────
# Graph schemas
# ──────────────────────────────────────────────

class NodeType(str, Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    API = "api"
    COMPONENT = "component"
    TEST = "test"
    VARIABLE = "variable"


class GraphNode(BaseModel):
    """Node in the knowledge graph."""
    id: str
    name: str
    node_type: NodeType
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    """Edge in the knowledge graph."""
    source: str
    target: str
    edge_type: DependencyType
    metadata: Dict[str, Any] = {}


class GraphData(BaseModel):
    """Serializable knowledge graph data."""
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []


# ──────────────────────────────────────────────
# Search schemas
# ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Search request."""
    query: str
    repo_id: int
    top_k: int = 10


class SearchResult(BaseModel):
    """A single search result."""
    chunk: CodeChunk
    score: float
    source: str = "vector"  # "vector", "graph", "code"


class SearchResponse(BaseModel):
    """Search response."""
    results: List[SearchResult]
    total: int
    query: str


class AssistantChatRequest(BaseModel):
    """AI Assistant conversational chat request."""
    repo_id: int
    message: str
    history: List[Dict[str, str]] = []


class AssistantChatResponse(BaseModel):
    """AI Assistant conversational chat response."""
    response: str
    relevant_chunks: List[SearchResult] = []
    suggested_followups: List[str] = []


# ──────────────────────────────────────────────
# Impact analysis schemas
# ──────────────────────────────────────────────

class ChangeRequest(BaseModel):
    """Request to analyze the impact of a code change."""
    repo_id: int
    query: str = Field(..., description="Natural language change description")
    target_function: Optional[str] = Field(None, description="Specific function name")
    target_file: Optional[str] = Field(None, description="Specific file path")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AffectedFile(BaseModel):
    """A file affected by the change."""
    file_path: str
    language: str
    risk_level: RiskLevel
    affected_functions: List[str] = []
    reason: str = ""
    dependency_depth: int = 0


class AffectedFunction(BaseModel):
    """A function affected by the change."""
    name: str
    qualified_name: str
    file_path: str
    risk_level: RiskLevel
    impact_type: str = ""  # "direct_caller", "indirect_caller", "shared_dependency"
    dependency_path: List[str] = []


class APIImpact(BaseModel):
    """An API endpoint affected by the change."""
    endpoint: str
    method: str = ""
    file_path: str
    risk_level: RiskLevel
    reason: str = ""


class TestRecommendation(BaseModel):
    """A recommended test to run."""
    test_name: str
    test_file: str
    priority: RiskLevel
    reason: str = ""
    covers: List[str] = []  # Functions/components this test covers


class Evidence(BaseModel):
    """Evidence supporting the impact analysis."""
    source: str  # "code_search", "rag_search", "graph_analysis"
    description: str
    code_snippet: Optional[str] = None
    file_path: Optional[str] = None
    line_range: Optional[str] = None
    confidence: float = 1.0


class VerificationResult(BaseModel):
    """Result of a verification check."""
    check_name: str
    passed: bool
    message: str
    severity: RiskLevel = RiskLevel.LOW


class ImpactReport(BaseModel):
    """The complete impact analysis report."""
    id: Optional[int] = None
    repo_id: int
    query: str
    status: str = "completed"

    # Changed component
    changed_component: str = ""
    changed_file: Optional[str] = None
    changed_function: Optional[str] = None

    # Impact data
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    affected_files: List[AffectedFile] = []
    affected_functions: List[AffectedFunction] = []
    dependency_paths: List[List[str]] = []
    api_impacts: List[APIImpact] = []

    # Test impact
    test_recommendations: List[TestRecommendation] = []
    estimated_test_coverage: float = 0.0

    # Evidence & reasoning
    evidence: List[Evidence] = []
    explanation: str = ""
    verification_results: List[VerificationResult] = []

    # Timestamps
    created_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None


# ──────────────────────────────────────────────
# Analysis history schemas
# ──────────────────────────────────────────────

class AnalysisSummary(BaseModel):
    """Summary of a past analysis."""
    id: int
    repo_id: int
    repo_name: str = ""
    query: str
    status: str
    risk_level: Optional[str]
    risk_score: Optional[float]
    affected_files_count: int
    affected_functions_count: int
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class AnalysisListResponse(BaseModel):
    """List of analyses."""
    analyses: List[AnalysisSummary]
    total: int
