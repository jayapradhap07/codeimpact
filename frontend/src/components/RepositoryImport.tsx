import React, { useState, useEffect } from "react";
import { api, RepositoryItem } from "../api/client";

interface RepositoryImportProps {
  onSelectRepo: (repoId: number) => void;
}

export const RepositoryImport: React.FC<RepositoryImportProps> = ({ onSelectRepo }) => {
  const [repoUrl, setRepoUrl] = useState("");
  const [customName, setCustomName] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [existingRepos, setExistingRepos] = useState<RepositoryItem[]>([]);

  const loadRepositories = async () => {
    try {
      const list = await api.listRepositories();
      setExistingRepos(list);
    } catch (e: any) {
      console.error("Failed to load existing repositories", e);
    }
  };

  useEffect(() => {
    loadRepositories();
  }, []);

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) {
      setError("Please enter a repository URL or local directory path.");
      return;
    }

    setError(null);
    setLoading(true);
    setStatusMessage("Cloning repository, scanning source files, and generating ChromaDB embeddings...");

    try {
      const result = await api.importRepository(repoUrl.trim(), customName.trim() || undefined);
      setStatusMessage("Repository imported and indexed successfully!");
      setRepoUrl("");
      setCustomName("");
      await loadRepositories();
      if (result && result.id) {
        onSelectRepo(result.id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to import repository.");
      setStatusMessage(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (repoId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to delete this repository?")) {
      try {
        await api.deleteRepository(repoId);
        await loadRepositories();
      } catch (err: any) {
        alert("Failed to delete: " + err.message);
      }
    }
  };

  return (
    <div className="section-container">
      <div className="card">
        <h2 className="title">1. IMPORT REPOSITORY</h2>
        <p className="subtitle">
          Enter a public GitHub repository URL or a local folder path to scan source code, create embeddings, and index into ChromaDB.
        </p>

        <form onSubmit={handleImport} className="form-group">
          <div className="form-row">
            <label className="label">GitHub Repository URL / Local Path:</label>
            <input
              type="text"
              className="input-text"
              placeholder="https://github.com/user/project"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-row">
            <label className="label">Custom Name (Optional):</label>
            <input
              type="text"
              className="input-text"
              placeholder="e.g. my-project"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="action-row">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? "Importing & Indexing..." : "Import Repository"}
            </button>
          </div>
        </form>

        {loading && (
          <div className="spinner-container">
            <div className="spinner"></div>
            <span>Importing and indexing repository into ChromaDB...</span>
          </div>
        )}

        {error && (
          <div className="error-box">
            <strong>Error:</strong> {error}
          </div>
        )}
      </div>

      {existingRepos.length > 0 && (
        <div className="card mt-20">
          <h3 className="section-heading">Imported Repositories</h3>
          <table className="simple-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Repository Name</th>
                <th>Source URL / Path</th>
                <th>Files</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {existingRepos.map((repo) => (
                <tr key={repo.id}>
                  <td>#{repo.id}</td>
                  <td className="font-bold">{repo.name}</td>
                  <td className="mono">{repo.url || "Local"}</td>
                  <td>{repo.total_files}</td>
                  <td>
                    <span className={`badge ${repo.status === "ready" ? "badge-ready" : "badge-error"}`}>
                      {repo.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <div className="btn-group">
                      <button
                        className="btn btn-sm"
                        onClick={() => onSelectRepo(repo.id)}
                        disabled={repo.status !== "ready"}
                      >
                        Open Dashboard
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={(e) => handleDelete(repo.id, e)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
