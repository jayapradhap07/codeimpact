"""Impact Engine.

Performs dependency analysis, change propagation, and risk scoring
based on the knowledge graph structure.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.models.schemas import (
    AffectedFile,
    AffectedFunction,
    APIImpact,
    DependencyType,
    Evidence,
    GraphNode,
    NodeType,
    RiskLevel,
)


class ImpactEngine:
    """Analyzes the impact of code changes through the knowledge graph."""

    # Risk weights by dependency depth
    DEPTH_RISK = {
        0: RiskLevel.CRITICAL,  # The changed element itself
        1: RiskLevel.HIGH,      # Direct dependents
        2: RiskLevel.MEDIUM,    # Indirect (2 hops)
        3: RiskLevel.LOW,       # Indirect (3+ hops)
    }

    def __init__(self, knowledge_graph: CodeKnowledgeGraph) -> None:
        self.graph = knowledge_graph

    # ──────────────────────────────────────────
    # Main analysis
    # ──────────────────────────────────────────

    def analyze_impact(
        self,
        target_node_id: str,
        max_depth: int = 4,
    ) -> Dict:
        """Run full impact analysis for a changed node.

        Returns a dict containing:
        - affected_files
        - affected_functions
        - dependency_paths
        - api_impacts
        - risk_level
        - risk_score
        - evidence
        """
        logger.info(f"Analyzing impact for: {target_node_id}")

        # 1. Find all affected nodes via BFS propagation
        affected = self.propagate_change(target_node_id, max_depth)

        # 2. Build affected files list
        affected_files = self._build_affected_files(target_node_id, affected)

        # 3. Build affected functions list
        affected_functions = self._build_affected_functions(target_node_id, affected)

        # 4. Find dependency paths
        dependency_paths = self._find_dependency_paths(target_node_id, affected)

        # 5. Find API impacts
        api_impacts = self._find_api_impacts(target_node_id, affected)

        # 6. Calculate risk
        risk_level, risk_score = self._calculate_risk(
            affected, affected_files, api_impacts
        )

        # 7. Collect evidence
        evidence = self._collect_evidence(
            target_node_id, affected, affected_files, api_impacts
        )

        return {
            "affected_files": affected_files,
            "affected_functions": affected_functions,
            "dependency_paths": dependency_paths,
            "api_impacts": api_impacts,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "evidence": evidence,
        }

    # ──────────────────────────────────────────
    # Change propagation
    # ──────────────────────────────────────────

    def propagate_change(
        self,
        node_id: str,
        max_depth: int = 4,
    ) -> List[Tuple[GraphNode, int]]:
        """Propagate a change through the graph using BFS.

        Returns list of (affected_node, depth) tuples.
        """
        if node_id not in self.graph.graph:
            return []

        affected: List[Tuple[GraphNode, int]] = []
        visited: Set[str] = {node_id}
        queue: List[Tuple[str, int]] = [(node_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth > max_depth:
                continue

            current_node = self.graph.get_node(current_id)
            if current_node and depth > 0:
                affected.append((current_node, depth))

            # Propagate to predecessors (who depends on this?)
            for pred in self.graph.graph.predecessors(current_id):
                if pred not in visited:
                    edge_data = self.graph.graph.edges[pred, current_id]
                    edge_type = edge_data.get("edge_type", "")

                    # Only propagate through meaningful relationships
                    if edge_type in (
                        DependencyType.CALLS.value,
                        DependencyType.IMPORTS.value,
                        DependencyType.USES.value,
                        DependencyType.DEPENDS_ON.value,
                        DependencyType.INHERITS.value,
                    ):
                        visited.add(pred)
                        queue.append((pred, depth + 1))

            # Also check containment (file → function)
            for pred in self.graph.graph.predecessors(current_id):
                if pred not in visited:
                    edge_data = self.graph.graph.edges[pred, current_id]
                    if edge_data.get("edge_type") == DependencyType.CONTAINS.value:
                        visited.add(pred)
                        queue.append((pred, depth))

        logger.info(f"Change propagation found {len(affected)} affected nodes")
        return affected

    # ──────────────────────────────────────────
    # Affected files
    # ──────────────────────────────────────────

    def _build_affected_files(
        self,
        target_id: str,
        affected: List[Tuple[GraphNode, int]],
    ) -> List[AffectedFile]:
        """Build the list of affected files with risk levels."""
        file_impacts: Dict[str, Dict] = {}

        for node, depth in affected:
            if not node.file_path:
                continue

            fp = node.file_path
            if fp not in file_impacts:
                file_impacts[fp] = {
                    "file_path": fp,
                    "language": node.language or "",
                    "risk_level": self._depth_to_risk(depth),
                    "affected_functions": [],
                    "min_depth": depth,
                    "reasons": set(),
                }

            info = file_impacts[fp]
            # Update risk to highest level
            if depth < info["min_depth"]:
                info["min_depth"] = depth
                info["risk_level"] = self._depth_to_risk(depth)

            if node.node_type in (NodeType.FUNCTION, NodeType.METHOD):
                info["affected_functions"].append(node.name)

            info["reasons"].add(
                f"{node.name} is {self._describe_relationship(depth)} the changed component"
            )

        return [
            AffectedFile(
                file_path=info["file_path"],
                language=info["language"],
                risk_level=info["risk_level"],
                affected_functions=info["affected_functions"],
                reason="; ".join(list(info["reasons"])[:3]),
                dependency_depth=info["min_depth"],
            )
            for info in sorted(
                file_impacts.values(), key=lambda x: x["min_depth"]
            )
        ]

    # ──────────────────────────────────────────
    # Affected functions
    # ──────────────────────────────────────────

    def _build_affected_functions(
        self,
        target_id: str,
        affected: List[Tuple[GraphNode, int]],
    ) -> List[AffectedFunction]:
        """Build the list of affected functions with impact types."""
        functions: List[AffectedFunction] = []

        for node, depth in affected:
            if node.node_type not in (NodeType.FUNCTION, NodeType.METHOD, NodeType.TEST):
                continue

            # Determine impact type
            if depth == 1:
                # Check if direct caller
                edge_data = self.graph.graph.edges.get((node.id, target_id))
                if edge_data and edge_data.get("edge_type") == DependencyType.CALLS.value:
                    impact_type = "direct_caller"
                else:
                    impact_type = "direct_dependent"
            elif depth == 2:
                impact_type = "indirect_caller"
            else:
                impact_type = "shared_dependency"

            # Find a dependency path
            paths = self.graph.get_impact_paths(node.id, target_id, max_paths=1)
            dep_path = paths[0] if paths else [node.id, target_id]

            functions.append(
                AffectedFunction(
                    name=node.name,
                    qualified_name=node.id,
                    file_path=node.file_path or "",
                    risk_level=self._depth_to_risk(depth),
                    impact_type=impact_type,
                    dependency_path=dep_path,
                )
            )

        return sorted(functions, key=lambda f: f.risk_level != RiskLevel.HIGH)

    # ──────────────────────────────────────────
    # Dependency paths
    # ──────────────────────────────────────────

    def _find_dependency_paths(
        self,
        target_id: str,
        affected: List[Tuple[GraphNode, int]],
    ) -> List[List[str]]:
        """Find notable dependency paths to the changed component."""
        paths: List[List[str]] = []

        for node, depth in affected:
            if depth <= 2 and node.node_type in (
                NodeType.FUNCTION,
                NodeType.METHOD,
                NodeType.API,
            ):
                found_paths = self.graph.get_impact_paths(
                    node.id, target_id, max_paths=2
                )
                paths.extend(found_paths)

        # Deduplicate and limit
        seen = set()
        unique_paths = []
        for p in paths:
            key = "->".join(p)
            if key not in seen:
                seen.add(key)
                unique_paths.append(p)

        return unique_paths[:20]

    # ──────────────────────────────────────────
    # API impacts
    # ──────────────────────────────────────────

    def _find_api_impacts(
        self,
        target_id: str,
        affected: List[Tuple[GraphNode, int]],
    ) -> List[APIImpact]:
        """Find API endpoints affected by the change."""
        apis: List[APIImpact] = []

        for node, depth in affected:
            if node.node_type == NodeType.API:
                apis.append(
                    APIImpact(
                        endpoint=node.metadata.get("path", node.name),
                        method=node.metadata.get("method", ""),
                        file_path=node.file_path or "",
                        risk_level=self._depth_to_risk(depth),
                        reason=f"API handler {self._describe_relationship(depth)} the changed component",
                    )
                )

        # Also check if any affected function has API decorators
        for node, depth in affected:
            if node.node_type in (NodeType.FUNCTION, NodeType.METHOD):
                decorators = node.metadata.get("decorators", [])
                for dec in decorators:
                    dec_lower = dec.lower()
                    for method in ("get", "post", "put", "delete", "patch"):
                        if f".{method}(" in dec_lower:
                            path = ""
                            if "(" in dec:
                                path = dec.split("(", 1)[1].rstrip(")").strip("'\"")
                            apis.append(
                                APIImpact(
                                    endpoint=path or f"/{node.name}",
                                    method=method.upper(),
                                    file_path=node.file_path or "",
                                    risk_level=self._depth_to_risk(depth),
                                    reason=f"Handler function is affected",
                                )
                            )

        return apis

    # ──────────────────────────────────────────
    # Risk calculation
    # ──────────────────────────────────────────

    def _calculate_risk(
        self,
        affected: List[Tuple[GraphNode, int]],
        affected_files: List[AffectedFile],
        api_impacts: List[APIImpact],
    ) -> Tuple[RiskLevel, float]:
        """Calculate overall risk level and score."""
        if not affected:
            return RiskLevel.LOW, 0.1

        # Risk factors
        num_affected = len(affected)
        num_files = len(affected_files)
        num_apis = len(api_impacts)
        min_depth = min(d for _, d in affected) if affected else 0

        # Check centrality
        centrality = self.graph.calculate_centrality()

        # Score components (0-1 each)
        affected_score = min(1.0, num_affected / 20)  # Cap at 20 affected nodes
        file_score = min(1.0, num_files / 10)          # Cap at 10 files
        api_score = min(1.0, num_apis / 3)             # Cap at 3 APIs
        depth_score = 1.0 - (min_depth / 5)            # Closer = higher risk

        # Centrality of the most affected nodes
        centrality_score = 0.0
        for node, _ in affected[:5]:
            centrality_score = max(
                centrality_score,
                centrality.get(node.id, 0.0),
            )
        centrality_score = min(1.0, centrality_score * 10)

        # Weighted combination
        risk_score = (
            affected_score * 0.25
            + file_score * 0.20
            + api_score * 0.25
            + depth_score * 0.15
            + centrality_score * 0.15
        )

        # Map to risk level
        if risk_score >= 0.75 or num_apis >= 2:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 0.50 or num_files >= 5:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 0.25 or num_files >= 3:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return risk_level, round(risk_score, 3)

    # ──────────────────────────────────────────
    # Evidence collection
    # ──────────────────────────────────────────

    def _collect_evidence(
        self,
        target_id: str,
        affected: List[Tuple[GraphNode, int]],
        affected_files: List[AffectedFile],
        api_impacts: List[APIImpact],
    ) -> List[Evidence]:
        """Collect evidence supporting the impact analysis."""
        evidence: List[Evidence] = []

        target_node = self.graph.get_node(target_id)
        if target_node:
            evidence.append(
                Evidence(
                    source="graph_analysis",
                    description=f"Changed component: {target_node.name} ({target_node.node_type.value})",
                    file_path=target_node.file_path,
                    line_range=f"L{target_node.start_line}-{target_node.end_line}",
                    confidence=1.0,
                )
            )

        # Direct callers
        callers = self.graph.get_callers(target_id)
        if callers:
            caller_names = [c.name for c in callers[:5]]
            evidence.append(
                Evidence(
                    source="graph_analysis",
                    description=f"Direct callers: {', '.join(caller_names)}",
                    confidence=0.95,
                )
            )

        # File impact evidence
        if affected_files:
            high_risk = [f for f in affected_files if f.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)]
            if high_risk:
                evidence.append(
                    Evidence(
                        source="graph_analysis",
                        description=f"{len(high_risk)} high-risk files affected",
                        confidence=0.9,
                    )
                )

        # API impact evidence
        for api in api_impacts:
            evidence.append(
                Evidence(
                    source="graph_analysis",
                    description=f"API endpoint affected: {api.method} {api.endpoint}",
                    file_path=api.file_path,
                    confidence=0.85,
                )
            )

        return evidence

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _depth_to_risk(self, depth: int) -> RiskLevel:
        """Map dependency depth to risk level."""
        if depth <= 0:
            return RiskLevel.CRITICAL
        elif depth == 1:
            return RiskLevel.HIGH
        elif depth == 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    @staticmethod
    def _describe_relationship(depth: int) -> str:
        """Describe the relationship based on depth."""
        if depth == 1:
            return "a direct dependent of"
        elif depth == 2:
            return "an indirect dependent of"
        else:
            return "transitively connected to"
