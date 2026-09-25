import React, { useState, useEffect } from "react";
import { api, HealthStatus } from "./api/client";
import { ImportRepository } from "./pages/ImportRepository";
import { Dashboard } from "./pages/Dashboard";

export const App: React.FC = () => {
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [checkingHealth, setCheckingHealth] = useState<boolean>(true);

  const checkOllamaHealth = async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setCheckingHealth(false);
    }
  };

  useEffect(() => {
    checkOllamaHealth();
    const interval = setInterval(checkOllamaHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <h1 className="header-title">AI Code Explanation &amp; Debugger Bot</h1>
          <span className="header-tag">RAG + Ollama</span>
        </div>

        <div className="header-right">
          {/* Ollama Status Indicator */}
          <div className="ollama-status">
            <span className="text-muted">Ollama:</span>{" "}
            {checkingHealth ? (
              <span className="badge badge-sm">Checking...</span>
            ) : health && health.ollama && health.ollama.available ? (
              <span className="badge badge-sm badge-ready">
                ONLINE ({health.ollama.configured_model || "Ready"})
              </span>
            ) : (
              <span className="badge badge-sm badge-error">
                OFFLINE (Start Ollama locally)
              </span>
            )}
          </div>

          <nav className="header-nav">
            <button
              className={`btn btn-sm ${!selectedRepoId ? "btn-primary" : ""}`}
              onClick={() => setSelectedRepoId(null)}
            >
              1. Import Repository
            </button>
            {selectedRepoId && (
              <button
                className="btn btn-sm btn-primary"
                onClick={() => {}}
              >
                2. Dashboard
              </button>
            )}
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="app-main">
        {!selectedRepoId ? (
          <ImportRepository onSelectRepo={(id) => setSelectedRepoId(id)} />
        ) : (
          <Dashboard
            repoId={selectedRepoId}
            onBackToImport={() => setSelectedRepoId(null)}
          />
        )}
      </main>

      {/* Minimal Footer */}
      <footer className="app-footer">
        <span>Simple RAG + Local Ollama Code Assistant</span>
        <span>Developer Tool</span>
      </footer>
    </div>
  );
};

export default App;
