"""Verification engine.

Cross-validates evidence from different search sources and performs
static checks on the impact analysis results.
"""

from __future__ import annotations

from typing import List

from loguru import logger

from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.models.schemas import (
    Evidence,
    ImpactReport,
    RiskLevel,
    VerificationResult,
)


class VerificationEngine:
    """Verifies and validates impact analysis results."""

    def __init__(self, knowledge_graph: CodeKnowledgeGraph) -> None:
        self.graph = knowledge_graph

    def verify_all(self, report: ImpactReport) -> List[VerificationResult]:
        """Run all verification checks on an impact report.

        Args:
            report: The impact report to verify.

        Returns:
            List of verification results.
        """
        results: List[VerificationResult] = []

        results.extend(self.verify_changed_component(report))
        results.extend(self.verify_dependencies(report))
        results.extend(self.verify_evidence(report))
        results.extend(self.verify_test_coverage(report))
        results.extend(self.verify_circular_dependencies(report))

        passed = sum(1 for r in results if r.passed)
        logger.info(
            f"Verification: {passed}/{len(results)} checks passed"
        )
        return results

    # ──────────────────────────────────────────
    # Individual checks
    # ──────────────────────────────────────────

    def verify_changed_component(
        self, report: ImpactReport
    ) -> List[VerificationResult]:
        """Verify that the changed component exists in the graph."""
        results: List[VerificationResult] = []

        if report.changed_function:
            # Check if the changed function exists in the graph
            nodes = self.graph.find_nodes_by_name(report.changed_function)
            found = any(
                n.name.lower() == report.changed_function.lower()
                for n in nodes
            )
            results.append(
                VerificationResult(
                    check_name="Changed component exists",
                    passed=found,
                    message=(
                        f"Function '{report.changed_function}' found in the knowledge graph"
                        if found
                        else f"Function '{report.changed_function}' NOT found in the knowledge graph"
                    ),
                    severity=RiskLevel.HIGH if not found else RiskLevel.LOW,
                )
            )

        if report.changed_file:
            node = self.graph.get_node(report.changed_file)
            results.append(
                VerificationResult(
                    check_name="Changed file exists",
                    passed=node is not None,
                    message=(
                        f"File '{report.changed_file}' found in the knowledge graph"
                        if node
                        else f"File '{report.changed_file}' NOT found in the knowledge graph"
                    ),
                    severity=RiskLevel.MEDIUM if not node else RiskLevel.LOW,
                )
            )

        return results

    def verify_dependencies(
        self, report: ImpactReport
    ) -> List[VerificationResult]:
        """Verify dependency paths are valid in the graph."""
        results: List[VerificationResult] = []

        if report.dependency_paths:
            valid_paths = 0
            for path in report.dependency_paths[:5]:
                # Check all nodes in the path exist
                all_exist = all(
                    node_id in self.graph.graph for node_id in path
                )
                if all_exist:
                    valid_paths += 1

            results.append(
                VerificationResult(
                    check_name="Dependency paths valid",
                    passed=valid_paths > 0,
                    message=f"{valid_paths}/{min(5, len(report.dependency_paths))} dependency paths verified in graph",
                    severity=RiskLevel.MEDIUM if valid_paths == 0 else RiskLevel.LOW,
                )
            )

        # Verify affected files exist in graph
        if report.affected_files:
            found_files = sum(
                1
                for f in report.affected_files
                if self.graph.get_node(f.file_path)
            )
            total = len(report.affected_files)
            results.append(
                VerificationResult(
                    check_name="Affected files verified",
                    passed=found_files == total,
                    message=f"{found_files}/{total} affected files confirmed in knowledge graph",
                    severity=RiskLevel.LOW,
                )
            )

        return results

    def verify_evidence(
        self, report: ImpactReport
    ) -> List[VerificationResult]:
        """Cross-validate evidence from different sources."""
        results: List[VerificationResult] = []

        if not report.evidence:
            results.append(
                VerificationResult(
                    check_name="Evidence available",
                    passed=False,
                    message="No evidence collected for this analysis",
                    severity=RiskLevel.HIGH,
                )
            )
            return results

        # Check evidence diversity (multiple sources)
        sources = set(e.source for e in report.evidence)
        results.append(
            VerificationResult(
                check_name="Evidence diversity",
                passed=len(sources) >= 2,
                message=f"Evidence from {len(sources)} source(s): {', '.join(sources)}",
                severity=RiskLevel.MEDIUM if len(sources) < 2 else RiskLevel.LOW,
            )
        )

        # Check average confidence
        avg_confidence = (
            sum(e.confidence for e in report.evidence) / len(report.evidence)
        )
        results.append(
            VerificationResult(
                check_name="Evidence confidence",
                passed=avg_confidence >= 0.7,
                message=f"Average evidence confidence: {avg_confidence:.2f}",
                severity=RiskLevel.MEDIUM if avg_confidence < 0.7 else RiskLevel.LOW,
            )
        )

        return results

    def verify_test_coverage(
        self, report: ImpactReport
    ) -> List[VerificationResult]:
        """Verify test coverage for affected components."""
        results: List[VerificationResult] = []

        if report.test_recommendations:
            critical_tests = [
                t
                for t in report.test_recommendations
                if t.priority in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            ]
            results.append(
                VerificationResult(
                    check_name="Test recommendations available",
                    passed=True,
                    message=f"{len(report.test_recommendations)} test(s) recommended, "
                    f"{len(critical_tests)} critical/high priority",
                    severity=RiskLevel.LOW,
                )
            )
        else:
            results.append(
                VerificationResult(
                    check_name="Test recommendations available",
                    passed=False,
                    message="No test recommendations generated — the changed component may lack test coverage",
                    severity=RiskLevel.HIGH,
                )
            )

        # Check estimated coverage
        if report.estimated_test_coverage < 0.25:
            results.append(
                VerificationResult(
                    check_name="Test coverage threshold",
                    passed=False,
                    message=f"Estimated test coverage is low ({report.estimated_test_coverage:.0%})",
                    severity=RiskLevel.HIGH,
                )
            )
        else:
            results.append(
                VerificationResult(
                    check_name="Test coverage threshold",
                    passed=True,
                    message=f"Estimated test coverage: {report.estimated_test_coverage:.0%}",
                    severity=RiskLevel.LOW,
                )
            )

        return results

    def verify_circular_dependencies(
        self, report: ImpactReport
    ) -> List[VerificationResult]:
        """Check for circular dependencies involving affected components."""
        results: List[VerificationResult] = []

        cycles = self.graph.find_cycles()
        if not cycles:
            results.append(
                VerificationResult(
                    check_name="Circular dependency check",
                    passed=True,
                    message="No circular dependencies detected",
                    severity=RiskLevel.LOW,
                )
            )
        else:
            # Check if any affected file is in a cycle
            affected_files = {f.file_path for f in report.affected_files}
            involved_cycles = [
                c
                for c in cycles
                if any(node in affected_files for node in c)
            ]

            if involved_cycles:
                results.append(
                    VerificationResult(
                        check_name="Circular dependency check",
                        passed=False,
                        message=f"{len(involved_cycles)} circular dependency cycle(s) involve affected files",
                        severity=RiskLevel.HIGH,
                    )
                )
            else:
                results.append(
                    VerificationResult(
                        check_name="Circular dependency check",
                        passed=True,
                        message=f"{len(cycles)} circular dependency cycles found but none involve affected files",
                        severity=RiskLevel.LOW,
                    )
                )

        return results
