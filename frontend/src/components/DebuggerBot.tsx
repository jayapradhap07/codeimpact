import React, { useState, useEffect } from "react";
import { api, RetrievedChunk } from "../api/client";
import { CodeViewer } from "./CodeViewer";

interface DebuggerBotProps {
  repoId: number;
  files: string[];
}

export const DebuggerBot: React.FC<DebuggerBotProps> = ({ repoId, files }) => {
  const [selectedFile, setSelectedFile] = useState<string>(files[0] || "");
  const [fileContent, setFileContent] = useState<string>("");
  const [debugQuery, setDebugQuery] = useState<string>("Find the error and tell me how to fix it.");
  const [loading, setLoading] = useState<boolean>(false);
  const [debugResult, setDebugResult] = useState<string | null>(null);
  const [retrievedChunks, setRetrievedChunks] = useState<RetrievedChunk[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (files.length > 0 && !selectedFile) {
      setSelectedFile(files[0]);
    }
  }, [files]);

  useEffect(() => {
    if (selectedFile && repoId) {
      loadFileContent(selectedFile);
    }
  }, [selectedFile, repoId]);

  const loadFileContent = async (path: string) => {
    try {
      setError(null);
      const res = await api.getFileContent(repoId, path);
      setFileContent(res.content);
    } catch (err: any) {
      setError(`Failed to load file: ${err.message}`);
      setFileContent("");
    }
  };

  const handleDebug = async (customQuery?: string) => {
    const q = customQuery || debugQuery;
    if (!selectedFile && !fileContent) {
      setError("Please select a file to debug.");
      return;
    }

    setError(null);
    setLoading(true);
    setDebugResult(null);
    setRetrievedChunks([]);

    try {
      const res = await api.debugCode({
        repo_id: repoId,
        file_path: selectedFile,
        code: fileContent,
        question: q,
      });

      setDebugResult(res.debug_result);
      setRetrievedChunks(res.retrieved_chunks || []);
    } catch (err: any) {
      setError(err.message || "Failed to analyze code with Ollama Debugger.");
    } finally {
      setLoading(false);
    }
  };

  const sampleDebugQueries = [
    "Why is this code failing?",
    "Find the error.",
    "Why am I getting this exception?",
    "How can I fix this?",
  ];

  return (
    <div className="feature-container">
      <div className="panel-row">
        {/* Left Column: File Selection & Code View */}
        <div className="panel-column left-panel">
          <div className="card">
            <h3 className="section-heading">Select File to Debug</h3>
            <div className="form-row">
              <label className="label">Repository Files ({files.length}):</label>
              <select
                className="select-input"
                value={selectedFile}
                onChange={(e) => setSelectedFile(e.target.value)}
              >
                {files.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-10">
              <CodeViewer filePath={selectedFile} code={fileContent} />
            </div>
          </div>
        </div>

        {/* Right Column: Debug Query & Analysis Output */}
        <div className="panel-column right-panel">
          <div className="card">
            <h3 className="section-heading">Debugger Bot</h3>

            <div className="quick-prompts">
              <span className="text-muted font-bold">Debug Inquiries:</span>
              <div className="prompt-buttons">
                {sampleDebugQueries.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={() => {
                      setDebugQuery(p);
                      handleDebug(p);
                    }}
                    disabled={loading}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-row mt-10">
              <label className="label">Error Description or Question:</label>
              <textarea
                className="textarea-input"
                rows={3}
                placeholder="Describe the exception, unexpected behavior, or what to look for..."
                value={debugQuery}
                onChange={(e) => setDebugQuery(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className="action-row">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleDebug()}
                disabled={loading || !selectedFile}
              >
                {loading ? "Searching RAG & Debugging with Ollama..." : "Debug Code"}
              </button>
            </div>

            {loading && (
              <div className="spinner-container">
                <div className="spinner"></div>
                <span>Analyzing code and finding bugs with Ollama...</span>
              </div>
            )}

            {error && (
              <div className="error-box mt-10">
                <strong>Error:</strong> {error}
              </div>
            )}

            {debugResult && (
              <div className="result-box mt-20">
                <h4 className="result-title">Debugging Report</h4>
                <div className="markdown-body">
                  <pre className="explanation-text">{debugResult}</pre>
                </div>
              </div>
            )}

            {retrievedChunks.length > 0 && (
              <div className="mt-20">
                <h4 className="font-bold">Retrieved Context References ({retrievedChunks.length}):</h4>
                <div className="chunks-list">
                  {retrievedChunks.map((chunk, idx) => (
                    <div key={idx} className="chunk-card">
                      <div className="chunk-header">
                        <span className="font-bold">
                          {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line})
                        </span>
                        <span className="badge badge-sm">{chunk.programming_language}</span>
                      </div>
                      <pre className="chunk-code">{chunk.content}</pre>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
