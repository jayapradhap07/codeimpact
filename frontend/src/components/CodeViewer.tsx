import React from "react";

interface CodeViewerProps {
  filePath: string;
  code: string;
  language?: string;
  highlightLines?: { start: number; end: number };
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  filePath,
  code,
  language = "code",
  highlightLines,
}) => {
  const lines = code ? code.split("\n") : [];

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    alert("Code copied to clipboard!");
  };

  return (
    <div className="code-viewer-container">
      <div className="code-viewer-header">
        <div className="code-viewer-title">
          <span className="font-bold">{filePath || "Source Code"}</span>
          <span className="badge badge-sm">{language}</span>
          <span className="text-muted">{lines.length} lines</span>
        </div>
        <button type="button" className="btn btn-sm" onClick={handleCopy}>
          Copy Code
        </button>
      </div>

      <div className="code-viewer-body">
        {lines.length === 0 ? (
          <div className="code-empty">No code content to display. Select a file from the repository.</div>
        ) : (
          <pre className="code-pre">
            <code>
              {lines.map((line, idx) => {
                const lineNum = idx + 1;
                const isHighlighted =
                  highlightLines &&
                  lineNum >= highlightLines.start &&
                  lineNum <= highlightLines.end;

                return (
                  <div
                    key={idx}
                    className={`code-line ${isHighlighted ? "code-line-highlight" : ""}`}
                  >
                    <span className="line-number">{lineNum}</span>
                    <span className="line-content">{line || " "}</span>
                  </div>
                );
              })}
            </code>
          </pre>
        )}
      </div>
    </div>
  );
};
