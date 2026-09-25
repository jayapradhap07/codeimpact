"""Code processor for syntax validation and intelligent code chunking."""

import ast
import re
from typing import List, Dict, Any, Tuple, Optional


class CodeProcessor:
    """Processes, validates, and splits source code into contextual chunks."""

    @staticmethod
    def validate_syntax(code: str, language: str) -> Tuple[bool, Optional[str]]:
        """Perform basic syntax checking where possible (e.g. Python)."""
        lang = language.lower().strip()
        if lang in ["python", "py"]:
            try:
                ast.parse(code)
                return True, None
            except SyntaxError as e:
                return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        return True, None

    @staticmethod
    def chunk_code(
        code: str,
        language: str = "python",
        chunk_lines: int = 15,
        overlap_lines: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Split source code into line-preserved, meaningful chunks with metadata.
        
        Each chunk contains:
        - chunk_id: unique identifier
        - content: code snippet
        - start_line: 1-indexed starting line in the original code
        - end_line: 1-indexed ending line in the original code
        - language: programming language
        - metadata: line_count, source
        """
        lines = code.splitlines()
        total_lines = len(lines)

        if total_lines == 0:
            return []

        # If code is small (fits in one or two small chunks), keep it simple
        if total_lines <= chunk_lines:
            return [
                {
                    "chunk_id": "chunk_1",
                    "content": code,
                    "start_line": 1,
                    "end_line": total_lines,
                    "language": language,
                    "metadata": {
                        "type": "full_snippet",
                        "line_count": total_lines,
                        "source": "user_input",
                    },
                }
            ]

        chunks: List[Dict[str, Any]] = []
        chunk_idx = 1
        step = max(1, chunk_lines - overlap_lines)
        start_idx = 0

        while start_idx < total_lines:
            end_idx = min(start_idx + chunk_lines, total_lines)
            chunk_content = "\n".join(lines[start_idx:end_idx])

            chunks.append(
                {
                    "chunk_id": f"chunk_{chunk_idx}",
                    "content": chunk_content,
                    "start_line": start_idx + 1,
                    "end_line": end_idx,
                    "language": language,
                    "metadata": {
                        "type": "window",
                        "line_count": end_idx - start_idx,
                        "source": "user_input",
                    },
                }
            )

            chunk_idx += 1
            if end_idx >= total_lines:
                break
            start_idx += step

        return chunks


code_processor = CodeProcessor()
