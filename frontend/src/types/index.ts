/* Types for the CodeImpact API */

// ── Repository ──

export interface Repository {
  id: number;
  name: string;
  url: string | null;
  local_path: string;
  status: 'pending' | 'cloning' | 'parsing' | 'indexing' | 'ready' | 'error';
  languages: Record<string, number> | null;
  file_count: number;
  function_count: number;
  class_count: number;
  total_lines: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface RepoListResponse {
  repositories: Repository[];
  total: number;
}

// ── Graph ──

export type NodeType = 'file' | 'class' | 'function' | 'method' | 'api' | 'component' | 'test' | 'variable';
export type EdgeType = 'imports' | 'calls' | 'uses' | 'depends_on' | 'inherits' | 'contains' | 'tests';

export interface GraphNode {
  id: string;
  name: string;
  node_type: NodeType;
  file_path: string | null;
  start_line: number | null;
  end_line: number | null;
  language: string | null;
  metadata: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  edge_type: EdgeType;
  metadata: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ── Search ──

export interface SearchRequest {
  query: string;
  repo_id: number;
  top_k?: number;
}

export interface CodeChunk {
  id: string;
  content: string;
  file_path: string;
  start_line: number;
  end_line: number;
  chunk_type: string;
  name: string;
  language: string;
  qualified_name: string;
  metadata: Record<string, any>;
}

export interface SearchResult {
  chunk: CodeChunk;
  score: number;
  source: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

// ── Analysis ──

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface ChangeRequest {
  repo_id: number;
  query: string;
  target_function?: string;
  target_file?: string;
}

export interface AffectedFile {
  file_path: string;
  language: string;
  risk_level: RiskLevel;
  affected_functions: string[];
  reason: string;
  dependency_depth: number;
}

export interface AffectedFunction {
  name: string;
  qualified_name: string;
  file_path: string;
  risk_level: RiskLevel;
  impact_type: string;
  dependency_path: string[];
}

export interface APIImpact {
  endpoint: string;
  method: string;
  file_path: string;
  risk_level: RiskLevel;
  reason: string;
}

export interface TestRecommendation {
  test_name: string;
  test_file: string;
  priority: RiskLevel;
  reason: string;
  covers: string[];
}

export interface Evidence {
  source: string;
  description: string;
  code_snippet: string | null;
  file_path: string | null;
  line_range: string | null;
  confidence: number;
}

export interface VerificationResult {
  check_name: string;
  passed: boolean;
  message: string;
  severity: RiskLevel;
}

export interface ImpactReport {
  id: number | null;
  repo_id: number;
  query: string;
  status: string;
  changed_component: string;
  changed_file: string | null;
  changed_function: string | null;
  risk_level: RiskLevel;
  risk_score: number;
  affected_files: AffectedFile[];
  affected_functions: AffectedFunction[];
  dependency_paths: string[][];
  api_impacts: APIImpact[];
  test_recommendations: TestRecommendation[];
  estimated_test_coverage: number;
  evidence: Evidence[];
  explanation: string;
  verification_results: VerificationResult[];
  created_at: string | null;
  completed_at: string | null;
}

export interface AnalysisSummary {
  id: number;
  repo_id: number;
  repo_name: string;
  query: string;
  status: string;
  risk_level: string | null;
  risk_score: number | null;
  affected_files_count: number;
  affected_functions_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface AnalysisListResponse {
  analyses: AnalysisSummary[];
  total: number;
}

// ── AI Assistant ──

export interface AssistantChatRequest {
  repo_id: number;
  message: string;
  history?: { role: string; content: string }[];
}

export interface AssistantChatResponse {
  response: string;
  relevant_chunks: SearchResult[];
  suggested_followups: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  relevant_chunks?: SearchResult[];
  suggested_followups?: string[];
  loading?: boolean;
}
