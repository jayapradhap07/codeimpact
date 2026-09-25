"""Code chunking for embedding generation.

Breaks parsed code into meaningful semantic chunks — one per function, class,
or significant block — suitable for vector embedding and RAG retrieval.
"""

from __future__ import annotations

import hashlib
from typing import List

from app.models.schemas import (
    ChunkType,
    CodeChunk,
    ParsedFile,
)


class CodeChunker:
    """Creates semantic code chunks from parsed files."""

    MAX_CHUNK_LINES = 100  # Split functions/classes larger than this
    OVERLAP_LINES = 10     # Overlap between split chunks

    def chunk_file(self, parsed_file: ParsedFile) -> List[CodeChunk]:
        """Create semantic chunks from a parsed file.

        Strategy:
        1. One chunk per function/method
        2. One chunk per class (header + attribute summary)
        3. Module-level chunk for imports + top-level code

        Args:
            parsed_file: A parsed source file.

        Returns:
            List of CodeChunk objects.
        """
        chunks: List[CodeChunk] = []
        lines = parsed_file.raw_content.split("\n") if parsed_file.raw_content else []

        if not lines:
            return chunks

        # 1. Module-level chunk (imports + top-level variables)
        module_chunk = self._create_module_chunk(parsed_file, lines)
        if module_chunk:
            chunks.append(module_chunk)

        # 2. Function chunks
        for func in parsed_file.functions:
            if not func.is_method:  # Methods are included via class chunks
                func_chunks = self._create_function_chunks(func, parsed_file, lines)
                chunks.extend(func_chunks)

        # 3. Class chunks
        for cls in parsed_file.classes:
            cls_chunks = self._create_class_chunks(cls, parsed_file, lines)
            chunks.extend(cls_chunks)

        return chunks

    def chunk_files(self, parsed_files: List[ParsedFile]) -> List[CodeChunk]:
        """Create chunks from multiple parsed files."""
        all_chunks: List[CodeChunk] = []
        for pf in parsed_files:
            all_chunks.extend(self.chunk_file(pf))
        return all_chunks

    # ──────────────────────────────────────────
    # Module-level chunk
    # ──────────────────────────────────────────

    def _create_module_chunk(
        self, parsed_file: ParsedFile, lines: List[str]
    ) -> CodeChunk | None:
        """Create a chunk for module-level code (imports, constants, docstring)."""
        # Gather import lines
        import_lines = []
        for imp in parsed_file.imports:
            start = imp.location.start_line - 1
            end = imp.location.end_line
            import_lines.extend(lines[start:end])

        # Gather top-level variable assignments (rough heuristic: first 50 lines)
        top_level = lines[:min(50, len(lines))]

        content_parts = []
        if import_lines:
            content_parts.append("# Imports\n" + "\n".join(import_lines))
        if parsed_file.variables:
            content_parts.append(
                "# Variables\n" + "\n".join(parsed_file.variables[:20])
            )

        if not content_parts:
            return None

        content = "\n\n".join(content_parts)
        return CodeChunk(
            id=self._make_id(parsed_file.file_path, "module", "module"),
            content=content,
            file_path=parsed_file.file_path,
            start_line=1,
            end_line=min(50, len(lines)),
            chunk_type=ChunkType.MODULE,
            name=parsed_file.file_path.split("/")[-1].split("\\")[-1],
            language=parsed_file.language,
            qualified_name=f"{parsed_file.file_path}::module",
        )

    # ──────────────────────────────────────────
    # Function chunks
    # ──────────────────────────────────────────

    def _create_function_chunks(
        self, func, parsed_file: ParsedFile, lines: List[str]
    ) -> List[CodeChunk]:
        """Create chunk(s) for a function. Large functions are split with overlap."""
        start = func.location.start_line - 1
        end = func.location.end_line
        func_lines = lines[start:end]
        func_content = "\n".join(func_lines)

        if len(func_lines) <= self.MAX_CHUNK_LINES:
            return [
                CodeChunk(
                    id=self._make_id(
                        parsed_file.file_path, "function", func.name
                    ),
                    content=func_content,
                    file_path=parsed_file.file_path,
                    start_line=func.location.start_line,
                    end_line=func.location.end_line,
                    chunk_type=ChunkType.FUNCTION,
                    name=func.name,
                    language=parsed_file.language,
                    qualified_name=func.qualified_name,
                    metadata={
                        "parameters": func.parameters,
                        "return_type": func.return_type,
                        "decorators": func.decorators,
                        "docstring": func.docstring,
                    },
                )
            ]

        # Split large functions with sliding window
        return self._split_large_block(
            func_lines,
            parsed_file.file_path,
            func.location.start_line,
            ChunkType.FUNCTION,
            func.name,
            parsed_file.language,
            func.qualified_name,
        )

    # ──────────────────────────────────────────
    # Class chunks
    # ──────────────────────────────────────────

    def _create_class_chunks(
        self, cls, parsed_file: ParsedFile, lines: List[str]
    ) -> List[CodeChunk]:
        """Create chunks for a class: one for the class header, one per method."""
        chunks: List[CodeChunk] = []
        start = cls.location.start_line - 1
        end = cls.location.end_line
        class_lines = lines[start:end]

        # Class header chunk (up to first method or max 30 lines)
        header_end = min(30, len(class_lines))
        if cls.methods:
            first_method_line = cls.methods[0].location.start_line - cls.location.start_line
            header_end = min(header_end, max(first_method_line, 5))

        header_content = "\n".join(class_lines[:header_end])
        chunks.append(
            CodeChunk(
                id=self._make_id(parsed_file.file_path, "class", cls.name),
                content=header_content,
                file_path=parsed_file.file_path,
                start_line=cls.location.start_line,
                end_line=cls.location.start_line + header_end - 1,
                chunk_type=ChunkType.CLASS,
                name=cls.name,
                language=parsed_file.language,
                qualified_name=cls.qualified_name,
                metadata={
                    "bases": cls.bases,
                    "method_count": len(cls.methods),
                    "docstring": cls.docstring,
                },
            )
        )

        # Individual method chunks
        for method in cls.methods:
            method_start = method.location.start_line - 1
            method_end = method.location.end_line
            method_lines = lines[method_start:method_end]
            method_content = "\n".join(method_lines)

            if len(method_lines) <= self.MAX_CHUNK_LINES:
                chunks.append(
                    CodeChunk(
                        id=self._make_id(
                            parsed_file.file_path,
                            "method",
                            f"{cls.name}.{method.name}",
                        ),
                        content=method_content,
                        file_path=parsed_file.file_path,
                        start_line=method.location.start_line,
                        end_line=method.location.end_line,
                        chunk_type=ChunkType.METHOD,
                        name=f"{cls.name}.{method.name}",
                        language=parsed_file.language,
                        qualified_name=method.qualified_name,
                        metadata={
                            "class_name": cls.name,
                            "parameters": method.parameters,
                            "decorators": method.decorators,
                            "docstring": method.docstring,
                        },
                    )
                )
            else:
                chunks.extend(
                    self._split_large_block(
                        method_lines,
                        parsed_file.file_path,
                        method.location.start_line,
                        ChunkType.METHOD,
                        f"{cls.name}.{method.name}",
                        parsed_file.language,
                        method.qualified_name,
                    )
                )

        return chunks

    # ──────────────────────────────────────────
    # Splitting
    # ──────────────────────────────────────────

    def _split_large_block(
        self,
        block_lines: List[str],
        file_path: str,
        global_start_line: int,
        chunk_type: ChunkType,
        name: str,
        language: str,
        qualified_name: str,
    ) -> List[CodeChunk]:
        """Split a large block into overlapping sub-chunks."""
        chunks: List[CodeChunk] = []
        total = len(block_lines)
        pos = 0
        part = 1

        while pos < total:
            end_pos = min(pos + self.MAX_CHUNK_LINES, total)
            segment = block_lines[pos:end_pos]
            content = "\n".join(segment)

            chunks.append(
                CodeChunk(
                    id=self._make_id(file_path, chunk_type.value, f"{name}_part{part}"),
                    content=content,
                    file_path=file_path,
                    start_line=global_start_line + pos,
                    end_line=global_start_line + end_pos - 1,
                    chunk_type=chunk_type,
                    name=f"{name} (part {part})",
                    language=language,
                    qualified_name=f"{qualified_name}::part{part}",
                )
            )

            pos = end_pos - self.OVERLAP_LINES
            if pos >= total - self.OVERLAP_LINES:
                break
            part += 1

        return chunks

    # ──────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────

    @staticmethod
    def _make_id(file_path: str, chunk_type: str, name: str) -> str:
        """Generate a unique chunk ID."""
        raw = f"{file_path}::{chunk_type}::{name}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]
