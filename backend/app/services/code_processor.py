"""Code processor for language detection, file filtering, and code chunking."""

from pathlib import Path
from typing import List, Dict, Any

# Supported code extensions and language names
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
}

# Directories to ignore during scan
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "build",
    "dist",
    "out",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    ".next",
    ".turbo",
    ".coverage",
    "htmlcov",
    ".gitattributes",
}

# Ignored binary/asset extensions
IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pyc", ".pyo", ".pyd", ".class", ".wasm",
    ".lock", ".sum", ".map", ".min.js", ".min.css",
    ".db", ".sqlite", ".sqlite3",
}


class CodeProcessor:
    """Processes source code files, extracts metadata, and chunks for RAG."""

    IGNORE_DIRS = IGNORE_DIRS
    IGNORE_EXTENSIONS = IGNORE_EXTENSIONS
    LANGUAGE_EXTENSIONS = LANGUAGE_EXTENSIONS

    @staticmethod
    def is_supported_file(file_path: Path) -> bool:
        """Check if file is a supported source code file."""
        if file_path.suffix.lower() in IGNORE_EXTENSIONS:
            return False
        return file_path.suffix.lower() in LANGUAGE_EXTENSIONS

    @staticmethod
    def get_language(file_path: str) -> str:
        """Detect language from file extension."""
        suffix = Path(file_path).suffix.lower()
        return LANGUAGE_EXTENSIONS.get(suffix, "text")

    @staticmethod
    def should_ignore_dir(dir_name: str) -> bool:
        """Check if directory name should be ignored."""
        return dir_name.lower() in IGNORE_DIRS or dir_name.startswith(".")

    @staticmethod
    def chunk_file_content(
        file_path: str,
        content: str,
        repo_name: str = "",
        chunk_lines: int = 25,
        overlap_lines: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Split a source file into line-preserved chunks with metadata:
        - chunk_id
        - repository
        - file_path
        - programming_language
        - start_line
        - end_line
        - content
        """
        lines = content.splitlines()
        total_lines = len(lines)
        language = CodeProcessor.get_language(file_path)

        if total_lines == 0:
            return []

        if total_lines <= chunk_lines:
            return [
                {
                    "chunk_id": f"{file_path}:1-{total_lines}",
                    "repository": repo_name,
                    "file_path": file_path,
                    "programming_language": language,
                    "start_line": 1,
                    "end_line": total_lines,
                    "content": content,
                }
            ]

        chunks: List[Dict[str, Any]] = []
        step = max(1, chunk_lines - overlap_lines)
        start_idx = 0

        while start_idx < total_lines:
            end_idx = min(start_idx + chunk_lines, total_lines)
            chunk_text = "\n".join(lines[start_idx:end_idx])
            start_line = start_idx + 1
            end_line = end_idx

            chunks.append(
                {
                    "chunk_id": f"{file_path}:{start_line}-{end_line}",
                    "repository": repo_name,
                    "file_path": file_path,
                    "programming_language": language,
                    "start_line": start_line,
                    "end_line": end_line,
                    "content": chunk_text,
                }
            )

            if end_idx >= total_lines:
                break
            start_idx += step

        return chunks


code_processor = CodeProcessor()
