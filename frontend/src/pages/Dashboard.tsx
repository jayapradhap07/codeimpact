import React, { useState, useEffect } from "react";
import { api, RepositoryItem } from "../api/client";
import { ExplainCode } from "../components/ExplainCode";
import { DebuggerBot } from "../components/DebuggerBot";

interface DashboardPageProps {
  repoId: number;
  onBackToImport: () => void;
}

export const Dashboard: React.FC<DashboardPageProps> = ({ repoId, onBackToImport }) => {
  const [repo, setRepo] = useState<RepositoryItem | null>(null);
  const [activeTab, setActiveTab] = useState<"explain" | "debug">("explain");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRepoDetails();
  }, [repoId]);

  const loadRepoDetails = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRepository(repoId);
      setRepo(data);
    } catch (err: any) {
      setError(err.message || "Failed to load repository details.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="card">
          <div className="spinner-container">
            <div className="spinner"></div>
            <span>Loading repository statistics...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !repo) {
    return (
      <div className="page-container">
        <div className="error-box">
          <strong>Error:</strong> {error || "Repository not found."}
          <div className="mt-10">
            <button className="btn btn-sm" onClick={onBackToImport}>
              &larr; Back to Import Repository
            </button>
          </div>
        </div>
      </div>
    );
  }

  const languages = repo.languages || {};
  const files = repo.files || [];

  return (
    <div className="page-container">
      {/* 2. DASHBOARD HEADER & STATS */}
      <div className="card mb-20">
        <div className="dashboard-header-row">
          <div>
            <h2 className="title">{repo.name}</h2>
            <p className="subtitle mono">{repo.url || "Local Repository"}</p>
          </div>
          <div>
            <button className="btn btn-sm" onClick={onBackToImport}>
              &larr; Switch / Import Repository
            </button>
          </div>
        </div>

        {/* Basic Statistics */}
        <div className="stats-grid mt-15">
          <div className="stat-card">
            <span className="stat-label">Total Files:</span>
            <span className="stat-value">{repo.total_files}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Supported Files:</span>
            <span className="stat-value">{repo.supported_files_count || files.length}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">ChromaDB Chunks:</span>
            <span className="stat-value">{repo.total_chunks || 0}</span>
          </div>
          <div className="stat-card languages-stat">
            <span className="stat-label">Languages:</span>
            <div className="lang-tags">
              {Object.keys(languages).length === 0 ? (
                <span className="text-muted">None detected</span>
              ) : (
                Object.entries(languages).map(([lang, count]) => (
                  <span key={lang} className="badge">
                    {lang}: {count}
                  </span>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Two Main Actions */}
        <div className="tab-navigation mt-20">
          <button
            className={`tab-btn ${activeTab === "explain" ? "tab-btn-active" : ""}`}
            onClick={() => setActiveTab("explain")}
          >
            3. Explain Code
          </button>
          <button
            className={`tab-btn ${activeTab === "debug" ? "tab-btn-active" : ""}`}
            onClick={() => setActiveTab("debug")}
          >
            4. Debugger Bot
          </button>
        </div>
      </div>

      {/* 3. EXPLAIN CODE OR 4. DEBUGGER BOT */}
      {activeTab === "explain" && <ExplainCode repoId={repo.id} files={files} />}
      {activeTab === "debug" && <DebuggerBot repoId={repo.id} files={files} />}
    </div>
  );
};
