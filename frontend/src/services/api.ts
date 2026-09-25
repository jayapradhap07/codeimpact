/* API client for the CodeImpact backend */

import type {
  AnalysisListResponse,
  ChangeRequest,
  GraphData,
  ImpactReport,
  RepoListResponse,
  Repository,
  SearchRequest,
  SearchResponse,
} from '../types';

const API_BASE = 'http://localhost:8000';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

// ── Repositories ──

export const api = {
  // Repositories
  async listRepositories(): Promise<RepoListResponse> {
    return request('/api/repositories');
  },

  async getRepository(id: number): Promise<Repository> {
    return request(`/api/repositories/${id}`);
  },

  async connectRepository(data: { url?: string; local_path?: string; name?: string }): Promise<Repository> {
    return request('/api/repositories', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async deleteRepository(id: number): Promise<void> {
    await fetch(`${API_BASE}/api/repositories/${id}`, { method: 'DELETE' });
  },

  async getRepositoryGraph(id: number): Promise<GraphData> {
    return request(`/api/repositories/${id}/graph`);
  },

  async getRepositoryStats(id: number): Promise<Record<string, any>> {
    return request(`/api/repositories/${id}/stats`);
  },

  // Analysis
  async runImpactAnalysis(data: ChangeRequest): Promise<ImpactReport> {
    return request('/api/analysis/impact', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getAnalysis(id: number): Promise<ImpactReport> {
    return request(`/api/analysis/${id}`);
  },

  async listAnalyses(repoId?: number): Promise<AnalysisListResponse> {
    const params = repoId ? `?repo_id=${repoId}` : '';
    return request(`/api/analysis/history/list${params}`);
  },

  // Search
  async searchCode(data: SearchRequest): Promise<SearchResponse> {
    return request('/api/search/code', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async searchSemantic(data: SearchRequest): Promise<SearchResponse> {
    return request('/api/search/semantic', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getGraphNeighborhood(repoId: number, nodeId: string, depth = 2): Promise<GraphData> {
    return request(`/api/search/graph/${repoId}/${encodeURIComponent(nodeId)}?depth=${depth}`);
  },

  // AI Assistant
  async askAssistant(data: { repo_id: number; message: string; history?: { role: string; content: string }[] }): Promise<any> {
    return request('/api/search/assistant', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // Health
  async healthCheck(): Promise<{ status: string }> {
    return request('/api/health');
  },
};

