"""Test impact analyzer.

Identifies tests related to a code change and generates
prioritized test recommendations.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from loguru import logger

from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.models.schemas import (
    GraphNode,
    NodeType,
    RiskLevel,
    TestRecommendation,
)


class TestImpactAnalyzer:
    """Analyzes the test impact of code changes."""

    def __init__(self, knowledge_graph: CodeKnowledgeGraph) -> None:
        self.graph = knowledge_graph

    def find_related_tests(
        self, target_node_id: str
    ) -> List[GraphNode]:
        """Find all tests related to the changed code.

        Searches for tests that:
        1. Directly call the changed function
        2. Are in a test file matching the source file pattern
        3. Test classes that use the changed component
        """
        return self.graph.find_related_tests(target_node_id)

    def recommend_tests(
        self,
        target_node_id: str,
        affected_nodes: List[Tuple[GraphNode, int]],
    ) -> List[TestRecommendation]:
        """Generate prioritized test recommendations.

        Args:
            target_node_id: The ID of the changed node.
            affected_nodes: List of (affected_node, depth) from impact analysis.

        Returns:
            Sorted list of test recommendations.
        """
        recommendations: List[TestRecommendation] = []
        seen_tests: set = set()

        # 1. Tests directly related to the changed component (highest priority)
        direct_tests = self.find_related_tests(target_node_id)
        for test_node in direct_tests:
            if test_node.id not in seen_tests:
                seen_tests.add(test_node.id)
                recommendations.append(
                    TestRecommendation(
                        test_name=test_node.name,
                        test_file=test_node.file_path or "",
                        priority=RiskLevel.CRITICAL,
                        reason=f"Directly tests the changed component",
                        covers=[target_node_id],
                    )
                )

        # 2. Tests related to affected components
        for node, depth in affected_nodes:
            related_tests = self.graph.find_related_tests(node.id)
            for test_node in related_tests:
                if test_node.id not in seen_tests:
                    seen_tests.add(test_node.id)
                    priority = self._depth_to_priority(depth)
                    recommendations.append(
                        TestRecommendation(
                            test_name=test_node.name,
                            test_file=test_node.file_path or "",
                            priority=priority,
                            reason=f"Tests {node.name} which is affected at depth {depth}",
                            covers=[node.id],
                        )
                    )

        # 3. Also recommend all test files in the same directory
        target_node = self.graph.get_node(target_node_id)
        if target_node and target_node.file_path:
            import os
            source_dir = os.path.dirname(target_node.file_path)
            all_tests = self.graph.get_all_nodes_by_type(NodeType.TEST)
            for test_node in all_tests:
                if test_node.id not in seen_tests:
                    if test_node.file_path and os.path.dirname(test_node.file_path) == source_dir:
                        seen_tests.add(test_node.id)
                        recommendations.append(
                            TestRecommendation(
                                test_name=test_node.name,
                                test_file=test_node.file_path,
                                priority=RiskLevel.LOW,
                                reason="Test in the same directory as the changed file",
                                covers=[],
                            )
                        )

        # Sort by priority (CRITICAL > HIGH > MEDIUM > LOW)
        priority_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
        }
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 4))

        logger.info(f"Generated {len(recommendations)} test recommendations")
        return recommendations

    def estimate_test_coverage(
        self, target_node_id: str
    ) -> float:
        """Estimate test coverage for a node.

        Returns a value between 0.0 (no tests) and 1.0 (well tested).
        """
        related_tests = self.find_related_tests(target_node_id)

        if not related_tests:
            return 0.0

        # Heuristic: more related tests = higher coverage estimate
        # Cap at 1.0
        return min(1.0, len(related_tests) * 0.25)

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _depth_to_priority(depth: int) -> RiskLevel:
        """Map dependency depth to test priority."""
        if depth <= 1:
            return RiskLevel.HIGH
        elif depth == 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
