import React, { useState, useEffect } from "react";
import { api, RetrievedChunk } from "../api/client";
import { CodeViewer } from "./CodeViewer";

interface ExplainCodeProps {
  repoId: number;
  files: string[];
}

export const ExplainCode: React.FC<ExplainCodeProps> = ({ repoId, files }) => {
  const [selectedFile, setSelectedFile] = useState<string>(files[0] || "");
  const [fileContent, setFileContent] = useState<string>("");
  const [question, setQuestion] = useState<string>("Explain this code.");
  const [loading, setLoading] = useState<boolean>(false);
  const [explanation, setExplanation] = useState<string | null>(null);
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

  const handleExplain = async (customQ?: string) => {
    const q = customQ || question;
    if (!selectedFile && !fileContent) {
      setError("Please select a file from the repository to explain.");
      return;
    }

    setError(null);
    setLoading(true);
    setExplanation(null);
    setRetrievedChunks([]);

    try {
      const res = await api.explainCode({
        repo_id: repoId,
        file_path: selectedFile,
        code: fileContent,
        question: q,
      });

      setExplanation(res.explanation);
      setRetrievedChunks(res.retrieved_chunks || []);
    } catch (err: any) {
      setError(err.message || "Failed to generate explanation from Ollama.");
    } finally {
      setLoading(false);
    }
  };

  const quickPrompts = [
    "Explain this code.",
    "Explain this function.",
    "What does this class do?",
    "Explain this code line by line.",
  ];

  return (
    <div className="feature-container">
      <div className="panel-row">
        {/* Left Column: File Selection & Code View */}
        <div className="panel-column left-panel">
          <div className="card">
            <h3 className="section-heading">Select File to Explain</h3>
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

        {/* Right Column: Question & Explanation */}
        <div className="panel-column right-panel">
          <div className="card">
            <h3 className="section-heading">Ask Explanation Question</h3>

            <div className="quick-prompts">
              <span className="text-muted font-bold">Quick Prompts:</span>
              <div className="prompt-buttons">
                {quickPrompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={() => {
                      setQuestion(p);
                      handleExplain(p);
                    }}
                    disabled={loading}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-row mt-10">
              <label className="label">Custom Question:</label>
              <textarea
                className="textarea-input"
                rows={3}
                placeholder="Ask anything about the code or repository logic..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className="action-row">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleExplain()}
                disabled={loading || !selectedFile}
              >
                {loading ? "Retrieving RAG Context & Asking Ollama..." : "Explain Code"}
              </button>
            </div>

            {loading && (
              <div className="spinner-container">
                <div className="spinner"></div>
                <span>Generating explanation with local Ollama...</span>
              </div>
            )}

            {error && (
              <div className="error-box mt-10">
                <strong>Error:</strong> {error}
              </div>
            )}

            {explanation && (
              <div className="result-box mt-20">
                <h4 className="result-title">AI Explanation (via Local Ollama)</h4>
                <div className="markdown-body">
                  <pre className="explanation-text">{explanation}</pre>
                </div>
              </div>
            )}

            {retrievedChunks.length > 0 && (
              <div className="mt-20">
                <h4 className="font-bold">Retrieved RAG Code Chunks ({retrievedChunks.length}):</h4>
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
