"""Code search engine.

Provides name-based and pattern-based code search across the knowledge graph
and source files.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from loguru import logger

from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.models.schemas import (
    ChunkType,
    CodeChunk,
    CodeLocation,
    GraphNode,
    SearchResult,
)


class CodeSearchEngine:
    """Searches code by name, pattern, or graph relationships."""

    def __init__(
        self,
        knowledge_graph: CodeKnowledgeGraph,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> None:
        self.graph = knowledge_graph
        self._file_contents = file_contents or {}

    def search_by_name(
        self, name: str, limit: int = 20
    ) -> List[SearchResult]:
        """Search for code elements by name (exact or partial match).

        Args:
            name: Function, class, or file name to search for.
            limit: Maximum results.

        Returns:
            List of SearchResult with matching code elements.
        """
        nodes = self.graph.find_nodes_by_name(name)

        # Sort by relevance: exact match first, then partial
        name_lower = name.lower()
        nodes.sort(
            key=lambda n: (
                0 if n.name.lower() == name_lower else 1,
                len(n.name),
            )
        )

        results: List[SearchResult] = []
        for node in nodes[:limit]:
            # Create a chunk from the graph node
            chunk = self._node_to_chunk(node)
            score = 1.0 if node.name.lower() == name_lower else 0.8
            results.append(
                SearchResult(chunk=chunk, score=score, source="code")
            )

        return results

    def search_by_pattern(
        self, pattern: str, limit: int = 20
    ) -> List[SearchResult]:
        """Search for code matching a regex pattern.

        Args:
            pattern: Regex pattern to search for.
            limit: Maximum results.

        Returns:
            List of SearchResult with matching code.
        """
        results: List[SearchResult] = []

        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            logger.warning(f"Invalid regex pattern: {pattern}")
            return results

        for file_path, content in self._file_contents.items():
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if compiled.search(line):
                    # Extract context around the match
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context = "\n".join(lines[start:end])

                    chunk = CodeChunk(
                        id=f"pattern_{file_path}_{i}",
                        content=context,
                        file_path=file_path,
                        start_line=start + 1,
                        end_line=end,
                        chunk_type=ChunkType.BLOCK,
                        name=f"Match at line {i + 1}",
                        language="",
                    )
                    results.append(
                        SearchResult(chunk=chunk, score=0.7, source="code")
                    )

                    if len(results) >= limit:
                        return results

        return results

    def search_callers(
        self, function_name: str
    ) -> List[SearchResult]:
        """Find all callers of a function.

        Args:
            function_name: Name of the function to find callers for.

        Returns:
            List of SearchResult with caller functions.
        """
        # Find the function node
        nodes = self.graph.find_nodes_by_name(function_name)
        if not nodes:
            return []

        results: List[SearchResult] = []
        for node in nodes:
            callers = self.graph.get_callers(node.id)
            for caller in callers:
                chunk = self._node_to_chunk(caller)
                results.append(
                    SearchResult(chunk=chunk, score=0.9, source="graph")
                )

        return results

    def search_related_components(
        self, node_id: str, depth: int = 2
    ) -> List[SearchResult]:
        """Find components related to a given node via the knowledge graph."""
        subgraph = self.graph.get_subgraph(node_id, depth)
        results: List[SearchResult] = []

        for node in subgraph.nodes:
            if node.id != node_id:
                chunk = self._node_to_chunk(node)
                results.append(
                    SearchResult(chunk=chunk, score=0.6, source="graph")
                )

        return results

    @staticmethod
    def _node_to_chunk(node: GraphNode) -> CodeChunk:
        """Convert a GraphNode to a CodeChunk for result formatting."""
        return CodeChunk(
            id=node.id,
            content=f"{node.node_type.value}: {node.name}",
            file_path=node.file_path or "",
            start_line=node.start_line or 0,
            end_line=node.end_line or 0,
            chunk_type=ChunkType(
                node.node_type.value
                if node.node_type.value in [e.value for e in ChunkType]
                else "block"
            ),
            name=node.name,
            language=node.language or "",
            qualified_name=node.id,
            metadata=node.metadata,
        )
