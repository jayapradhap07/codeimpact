"""Code Knowledge Graph.

Builds and queries a directed graph of code relationships using NetworkX.
Nodes represent code elements (files, classes, functions, tests, APIs).
Edges represent relationships (contains, calls, imports, inherits, tests).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import networkx as nx
from loguru import logger

from app.models.schemas import (
    Dependency,
    DependencyType,
    GraphData,
    GraphEdge,
    GraphNode,
    NodeType,
    ParsedFile,
)


class CodeKnowledgeGraph:
    """Knowledge graph representing code structure and relationships."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._node_data: Dict[str, GraphNode] = {}

    # ──────────────────────────────────────────
    # Construction
    # ──────────────────────────────────────────

    def build_from_analysis(
        self,
        parsed_files: List[ParsedFile],
        dependencies: List[Dependency],
    ) -> None:
        """Build the full knowledge graph from parsed files and dependencies.

        Args:
            parsed_files: All parsed source files.
            dependencies: All discovered dependencies.
        """
        logger.info("Building knowledge graph...")

        # 1. Add file nodes
        for pf in parsed_files:
            self._add_file_node(pf)

        # 2. Add function and class nodes
        for pf in parsed_files:
            for func in pf.functions:
                node_type = NodeType.METHOD if func.is_method else NodeType.FUNCTION
                # Check if it's a test
                if self._is_test(func.name, pf.file_path):
                    node_type = NodeType.TEST

                self._add_node(
                    node_id=func.qualified_name,
                    name=func.name,
                    node_type=node_type,
                    file_path=pf.file_path,
                    start_line=func.location.start_line,
                    end_line=func.location.end_line,
                    language=pf.language,
                    metadata={
                        "parameters": func.parameters,
                        "return_type": func.return_type,
                        "docstring": func.docstring,
                        "decorators": func.decorators,
                        "is_method": func.is_method,
                        "class_name": func.class_name,
                    },
                )

            for cls in pf.classes:
                self._add_node(
                    node_id=cls.qualified_name,
                    name=cls.name,
                    node_type=NodeType.CLASS,
                    file_path=pf.file_path,
                    start_line=cls.location.start_line,
                    end_line=cls.location.end_line,
                    language=pf.language,
                    metadata={
                        "bases": cls.bases,
                        "method_count": len(cls.methods),
                        "docstring": cls.docstring,
                    },
                )

        # 3. Add API endpoint nodes
        for pf in parsed_files:
            for func in pf.functions:
                api_info = self._detect_api_endpoint(func)
                if api_info:
                    api_id = f"api::{api_info['method']}::{api_info['path']}"
                    self._add_node(
                        node_id=api_id,
                        name=f"{api_info['method']} {api_info['path']}",
                        node_type=NodeType.API,
                        file_path=pf.file_path,
                        start_line=func.location.start_line,
                        end_line=func.location.end_line,
                        language=pf.language,
                        metadata=api_info,
                    )
                    # Link API to its handler function
                    self._add_edge(api_id, func.qualified_name, DependencyType.DEPENDS_ON)

        # 4. Add all dependency edges
        for dep in dependencies:
            self._add_edge(dep.source, dep.target, dep.dep_type, dep.metadata)

        logger.info(
            f"Knowledge graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self._node_data.get(node_id)

    def get_dependents(self, node_id: str, max_depth: int = 3) -> List[GraphNode]:
        """Find all nodes that depend on (are affected by changes to) the given node.

        This traverses INCOMING edges (who calls/imports/uses this node).
        """
        if node_id not in self.graph:
            return []

        dependents: Set[str] = set()
        self._bfs_predecessors(node_id, max_depth, dependents)

        return [
            self._node_data[n]
            for n in dependents
            if n in self._node_data and n != node_id
        ]

    def get_dependencies(self, node_id: str, max_depth: int = 3) -> List[GraphNode]:
        """Find all nodes that the given node depends on.

        This traverses OUTGOING edges.
        """
        if node_id not in self.graph:
            return []

        dependencies: Set[str] = set()
        self._bfs_successors(node_id, max_depth, dependencies)

        return [
            self._node_data[n]
            for n in dependencies
            if n in self._node_data and n != node_id
        ]

    def get_callers(self, node_id: str) -> List[GraphNode]:
        """Find direct callers of a function/method."""
        if node_id not in self.graph:
            return []

        callers = []
        for pred in self.graph.predecessors(node_id):
            edge_data = self.graph.edges[pred, node_id]
            if edge_data.get("edge_type") == DependencyType.CALLS.value:
                node = self._node_data.get(pred)
                if node:
                    callers.append(node)
        return callers

    def get_callees(self, node_id: str) -> List[GraphNode]:
        """Find functions/methods called by the given node."""
        if node_id not in self.graph:
            return []

        callees = []
        for succ in self.graph.successors(node_id):
            edge_data = self.graph.edges[node_id, succ]
            if edge_data.get("edge_type") == DependencyType.CALLS.value:
                node = self._node_data.get(succ)
                if node:
                    callees.append(node)
        return callees

    def get_impact_paths(
        self, source: str, target: str, max_paths: int = 5
    ) -> List[List[str]]:
        """Find dependency paths between two nodes."""
        if source not in self.graph or target not in self.graph:
            return []

        try:
            paths = list(
                nx.all_simple_paths(
                    self.graph, source, target, cutoff=10
                )
            )
            return paths[:max_paths]
        except nx.NetworkXError:
            return []

    def get_subgraph(
        self, node_id: str, depth: int = 2
    ) -> GraphData:
        """Extract a local neighborhood subgraph around a node.

        Returns nodes and edges within `depth` hops of the given node.
        """
        if node_id not in self.graph:
            return GraphData()

        # Collect nodes within depth (both directions)
        nearby_nodes: Set[str] = {node_id}

        # Forward (successors)
        self._bfs_successors(node_id, depth, nearby_nodes)
        # Backward (predecessors)
        self._bfs_predecessors(node_id, depth, nearby_nodes)

        # Build subgraph data
        nodes = [
            self._node_data[n] for n in nearby_nodes if n in self._node_data
        ]
        edges = []
        for u, v, data in self.graph.edges(data=True):
            if u in nearby_nodes and v in nearby_nodes:
                edges.append(
                    GraphEdge(
                        source=u,
                        target=v,
                        edge_type=DependencyType(data.get("edge_type", "depends_on")),
                        metadata=data.get("metadata", {}),
                    )
                )

        return GraphData(nodes=nodes, edges=edges)

    def find_related_tests(self, node_id: str) -> List[GraphNode]:
        """Find test nodes that are related to the given node."""
        tests: List[GraphNode] = []

        # Direct test relationships
        for pred in self.graph.predecessors(node_id):
            node = self._node_data.get(pred)
            if node and node.node_type == NodeType.TEST:
                tests.append(node)

        # Tests in the same file
        source_node = self._node_data.get(node_id)
        if source_node and source_node.file_path:
            for nid, ndata in self._node_data.items():
                if (
                    ndata.node_type == NodeType.TEST
                    and ndata.file_path
                    and nid != node_id
                ):
                    # Check if test file matches naming pattern
                    if self._is_related_test_file(
                        source_node.file_path, ndata.file_path
                    ):
                        if ndata not in tests:
                            tests.append(ndata)

        # Tests that call this function
        if node_id in self.graph:
            for pred in self.graph.predecessors(node_id):
                edge_data = self.graph.edges[pred, node_id]
                if edge_data.get("edge_type") == DependencyType.CALLS.value:
                    pred_node = self._node_data.get(pred)
                    if pred_node and pred_node.node_type == NodeType.TEST:
                        if pred_node not in tests:
                            tests.append(pred_node)

        return tests

    def find_nodes_by_name(self, name: str) -> List[GraphNode]:
        """Search for nodes by name (exact or partial match)."""
        results = []
        name_lower = name.lower()
        for nid, node in self._node_data.items():
            if name_lower in node.name.lower():
                results.append(node)
        return results

    def get_all_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Get all nodes of a specific type."""
        return [n for n in self._node_data.values() if n.node_type == node_type]

    def calculate_centrality(self) -> Dict[str, float]:
        """Calculate PageRank centrality for all nodes with fallback."""
        if self.graph.number_of_nodes() == 0:
            return {}
        try:
            return nx.pagerank(self.graph, max_iter=100)
        except Exception:
            return nx.degree_centrality(self.graph)

    def find_cycles(self) -> List[List[str]]:
        """Find circular dependencies."""
        try:
            return list(nx.simple_cycles(self.graph))
        except Exception:
            return []

    # ──────────────────────────────────────────
    # Serialization
    # ──────────────────────────────────────────

    def serialize(self) -> GraphData:
        """Serialize the entire graph to a GraphData object."""
        nodes = list(self._node_data.values())
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append(
                GraphEdge(
                    source=u,
                    target=v,
                    edge_type=DependencyType(data.get("edge_type", "depends_on")),
                    metadata=data.get("metadata", {}),
                )
            )
        return GraphData(nodes=nodes, edges=edges)

    def save(self, path: str) -> None:
        """Save the graph to a JSON file."""
        data = self.serialize()
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data.model_dump(), f, indent=2, default=str)
        logger.info(f"Graph saved to {path}")

    def load(self, path: str) -> None:
        """Load the graph from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        data = GraphData(**raw)
        self.graph.clear()
        self._node_data.clear()

        for node in data.nodes:
            self._node_data[node.id] = node
            self.graph.add_node(node.id, **node.model_dump())

        for edge in data.edges:
            self.graph.add_edge(
                edge.source,
                edge.target,
                edge_type=edge.edge_type.value,
                metadata=edge.metadata,
            )

        logger.info(
            f"Graph loaded from {path}: "
            f"{self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    # ──────────────────────────────────────────
    # Stats
    # ──────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics about the graph."""
        type_counts: Dict[str, int] = {}
        for node in self._node_data.values():
            t = node.node_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        edge_type_counts: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            t = data.get("edge_type", "unknown")
            edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": type_counts,
            "edge_types": edge_type_counts,
            "connected_components": (
                nx.number_weakly_connected_components(self.graph)
                if self.graph.number_of_nodes() > 0
                else 0
            ),
        }

    # ──────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────

    def _add_file_node(self, parsed_file: ParsedFile) -> None:
        """Add a file node to the graph."""
        self._add_node(
            node_id=parsed_file.file_path,
            name=parsed_file.file_path.split("/")[-1].split("\\")[-1],
            node_type=NodeType.FILE,
            file_path=parsed_file.file_path,
            language=parsed_file.language,
            metadata={
                "line_count": parsed_file.line_count,
                "function_count": len(parsed_file.functions),
                "class_count": len(parsed_file.classes),
                "import_count": len(parsed_file.imports),
            },
        )

    def _add_node(
        self,
        node_id: str,
        name: str,
        node_type: NodeType,
        file_path: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        language: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a node to the graph."""
        node = GraphNode(
            id=node_id,
            name=name,
            node_type=node_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=language,
            metadata=metadata or {},
        )
        self._node_data[node_id] = node
        self.graph.add_node(node_id, **node.model_dump())

    def _add_edge(
        self,
        source: str,
        target: str,
        edge_type: DependencyType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an edge to the graph."""
        # Ensure both nodes exist (add placeholder if needed)
        if source not in self.graph:
            self.graph.add_node(source)
        if target not in self.graph:
            self.graph.add_node(target)

        self.graph.add_edge(
            source,
            target,
            edge_type=edge_type.value,
            metadata=metadata or {},
        )

    def _bfs_predecessors(
        self, node_id: str, max_depth: int, visited: Set[str]
    ) -> None:
        """BFS over predecessors (incoming edges)."""
        queue = [(node_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for pred in self.graph.predecessors(current):
                if pred not in visited:
                    visited.add(pred)
                    queue.append((pred, depth + 1))

    def _bfs_successors(
        self, node_id: str, max_depth: int, visited: Set[str]
    ) -> None:
        """BFS over successors (outgoing edges)."""
        queue = [(node_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for succ in self.graph.successors(current):
                if succ not in visited:
                    visited.add(succ)
                    queue.append((succ, depth + 1))

    @staticmethod
    def _is_test(func_name: str, file_path: str) -> bool:
        """Check if a function/file is a test."""
        name_lower = func_name.lower()
        path_lower = file_path.lower().replace("\\", "/")

        return (
            name_lower.startswith("test_")
            or name_lower.startswith("test")
            or name_lower.endswith("_test")
            or "test/" in path_lower
            or "tests/" in path_lower
            or "__tests__/" in path_lower
            or path_lower.endswith("_test.py")
            or path_lower.endswith(".test.js")
            or path_lower.endswith(".test.ts")
            or path_lower.endswith(".spec.js")
            or path_lower.endswith(".spec.ts")
        )

    @staticmethod
    def _is_related_test_file(source_path: str, test_path: str) -> bool:
        """Check if a test file is related to a source file."""
        import os
        source_name = os.path.splitext(os.path.basename(source_path))[0]
        test_name = os.path.splitext(os.path.basename(test_path))[0]

        return (
            test_name == f"test_{source_name}"
            or test_name == f"{source_name}_test"
            or test_name == f"{source_name}.test"
            or test_name == f"{source_name}.spec"
        )

    @staticmethod
    def _detect_api_endpoint(func) -> Optional[Dict[str, str]]:
        """Detect if a function is an API endpoint handler."""
        for decorator in func.decorators:
            dec_lower = decorator.lower()
            for method in ("get", "post", "put", "delete", "patch"):
                if f".{method}(" in dec_lower or f"@{method}" in dec_lower:
                    # Try to extract path
                    path = ""
                    if "(" in decorator:
                        path_part = decorator.split("(", 1)[1].rstrip(")")
                        path = path_part.strip("'\"").split(",")[0].strip("'\"")
                    return {
                        "method": method.upper(),
                        "path": path or f"/{func.name}",
                        "handler": func.name,
                    }
        return None
