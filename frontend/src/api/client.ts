/**
 * API client for interacting with the backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface HealthStatus {
  status: string;
  app_name: string;
  version: string;
  ollama: {
    available: boolean;
    configured_model?: string;
    available_models?: string[];
    model_ready?: boolean;
    error?: string;
  };
}

export interface RepositoryItem {
  id: number;
  name: string;
  url?: string;
  status: string;
  total_files: number;
  supported_files_count?: number;
  languages?: Record<string, number>;
  files?: string[];
  total_chunks?: number;
  error_message?: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  programming_language: string;
  content: string;
}

export interface ExplainResponse {
  explanation: string;
  file_path: string;
  question: string;
  retrieved_chunks: RetrievedChunk[];
}

export interface DebugResponse {
  debug_result: string;
  file_path: string;
  question: string;
  retrieved_chunks: RetrievedChunk[];
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      let errDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorData = await res.json();
        if (errorData.detail) {
          errDetail = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // use default error text
      }
      throw new Error(errDetail);
    }
    return await res.json();
  } catch (err: any) {
    if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
      throw new Error(`Cannot reach backend server at ${API_BASE_URL}. Ensure FastAPI is running on port 8000.`);
    }
    throw err;
  }
}

export const api = {
  getHealth: () => request<HealthStatus>("/api/health"),

  importRepository: (url_or_path: string, custom_name?: string) =>
    request<RepositoryItem>("/api/repositories/import", {
      method: "POST",
      body: JSON.stringify({ url_or_path, custom_name }),
    }),

  listRepositories: () => request<RepositoryItem[]>("/api/repositories"),

  getRepository: (repoId: number) => request<RepositoryItem>(`/api/repositories/${repoId}`),

  getFileContent: (repoId: number, filePath: string) =>
    request<{ file_path: string; content: string }>(
      `/api/repositories/${repoId}/file?path=${encodeURIComponent(filePath)}`
    ),

  deleteRepository: (repoId: number) =>
    request<{ status: string; id: number }>(`/api/repositories/${repoId}`, {
      method: "DELETE",
    }),

  deleteRepositoryFile: (repoId: number, filePath: string) =>
    request<{ status: string; repo_id: number; file_path: string }>(
      `/api/repositories/${repoId}/file?path=${encodeURIComponent(filePath)}`,
      {
        method: "DELETE",
      }
    ),


  explainCode: (data: { repo_id: number; file_path?: string; code?: string; question?: string }) =>
    request<ExplainResponse>("/api/explain", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  debugCode: (data: { repo_id: number; file_path?: string; code?: string; question?: string }) =>
    request<DebugResponse>("/api/debug", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
