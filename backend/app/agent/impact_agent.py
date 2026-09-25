"""Impact Agent — Single Agentic AI Orchestration Layer.

Orchestrates codebase intelligence tools:
  1. Code Search (symbol/pattern search)
  2. RAG Retrieval (vector similarity search + context expansion)
  3. Dependency Analysis (AST call graph inspection)
  4. Knowledge Graph Traversal (neighborhood & hierarchy discovery)
  5. Impact Engine (deterministic change propagation & risk scoring)
  6. Test Impact Analysis (test coverage & prioritized test recommendations)
  7. Verification Engine (multi-source cross-validation)

Reasoning is powered by local LLMs (e.g. Ollama qwen2.5-coder:7b) via the LLM provider abstraction.
"""

from __future__ import annotations

import datetime
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from app.agent.impact_engine import ImpactEngine
from app.agent.test_impact import TestImpactAnalyzer
from app.agent.verification import VerificationEngine
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.llm.prompts import (
    SYSTEM_PROMPT,
    build_assistant_prompt,
    build_explanation_prompt,
    build_understanding_prompt,
)
from app.llm.provider import FallbackProvider, LLMProvider, get_provider
from app.models.schemas import (
    AssistantChatResponse,
    ChangeRequest,
    Evidence,
    GraphData,
    GraphNode,
    ImpactReport,
    NodeType,
    RiskLevel,
    SearchResult,
    TestRecommendation,
    VerificationResult,
)
from app.search.code_search import CodeSearchEngine
from app.search.rag import RAGEngine


class ImpactAgent:
    """Agentic AI Orchestrator for Code Impact Analysis and Codebase Intelligence."""

    MAX_TOOL_ITERATIONS = 8

    def __init__(
        self,
        knowledge_graph: CodeKnowledgeGraph,
        rag_engine: RAGEngine,
        code_search: CodeSearchEngine,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self.graph = knowledge_graph
        self.rag_engine = rag_engine
        self.code_search = code_search
        self.llm = llm_provider or get_provider()

        # Deterministic analysis sub-engines
        self.impact_engine = ImpactEngine(knowledge_graph)
        self.test_analyzer = TestImpactAnalyzer(knowledge_graph)
        self.verifier = VerificationEngine(knowledge_graph)

    # ─────────────────────────────────────────────────────────────
    # Agent Tools
    # ─────────────────────────────────────────────────────────────

    def search_code(self, query_or_name: str, limit: int = 15) -> List[SearchResult]:
        """Tool 1: Search code elements by exact/fuzzy name or regex pattern."""
        results: List[SearchResult] = []
        try:
            # 1. Name-based search
            name_results = self.code_search.search_by_name(query_or_name, limit=limit)
            results.extend(name_results)

            # 2. If few results, attempt regex pattern search
            if len(results) < 3:
                pattern_results = self.code_search.search_by_pattern(query_or_name, limit=limit)
                results.extend(pattern_results)
        except Exception as e:
            logger.warning(f"Tool search_code failed for '{query_or_name}': {e}")
        return results

    def retrieve_rag_context(self, query: str, k: int = 5, context_lines: int = 10) -> List[SearchResult]:
        """Tool 2: Semantic RAG vector retrieval with surrounding source context."""
        try:
            return self.rag_engine.search_with_context(query, k=k, context_lines=context_lines)
        except Exception as e:
            logger.warning(f"Tool retrieve_rag_context failed for '{query}': {e}")
            return []

    def analyze_dependencies(self, node_id: str) -> Dict[str, Any]:
        """Tool 3: Extract direct callers, callees, and dependents from the AST graph."""
        try:
            node = self.graph.get_node(node_id)
            callers = self.graph.get_callers(node_id)
            callees = self.graph.get_callees(node_id)
            dependents = self.graph.get_dependents(node_id, max_depth=2)

            return {
                "node": node,
                "callers": callers,
                "callees": callees,
                "dependents": dependents,
            }
        except Exception as e:
            logger.warning(f"Tool analyze_dependencies failed for '{node_id}': {e}")
            return {"node": None, "callers": [], "callees": [], "dependents": []}

    def traverse_knowledge_graph(self, node_id: str, depth: int = 2) -> GraphData:
        """Tool 4: Traverse the graph to extract local topological neighborhood."""
        try:
            return self.graph.get_subgraph(node_id, depth=depth)
        except Exception as e:
            logger.warning(f"Tool traverse_knowledge_graph failed for '{node_id}': {e}")
            return GraphData(nodes=[], edges=[])

    def calculate_impact(self, node_id: str, max_depth: int = 4) -> Dict[str, Any]:
        """Tool 5: Deterministically compute change propagation, blast radius, and risk score."""
        try:
            return self.impact_engine.analyze_impact(node_id, max_depth=max_depth)
        except Exception as e:
            logger.error(f"Tool calculate_impact failed for '{node_id}': {e}")
            return {
                "affected_files": [],
                "affected_functions": [],
                "dependency_paths": [],
                "api_impacts": [],
                "risk_level": RiskLevel.LOW,
                "risk_score": 0.0,
                "evidence": [],
            }

    def find_related_tests(
        self,
        node_id: str,
        affected_nodes: Optional[List[Tuple[GraphNode, int]]] = None,
    ) -> Dict[str, Any]:
        """Tool 6: Identify tests covering the target and its impacted components."""
        try:
            direct_tests = self.test_analyzer.find_related_tests(node_id)
            coverage = self.test_analyzer.estimate_test_coverage(node_id)
            recommendations: List[TestRecommendation] = []
            if affected_nodes is not None:
                recommendations = self.test_analyzer.recommend_tests(node_id, affected_nodes)
            return {
                "direct_tests": direct_tests,
                "coverage": coverage,
                "recommendations": recommendations,
            }
        except Exception as e:
            logger.warning(f"Tool find_related_tests failed for '{node_id}': {e}")
            return {"direct_tests": [], "coverage": 0.0, "recommendations": []}

    def verify_results(self, report: ImpactReport) -> List[VerificationResult]:
        """Tool 7: Multi-source verification validating evidence against AST ground truth."""
        try:
            return self.verifier.verify_all(report)
        except Exception as e:
            logger.warning(f"Tool verify_results failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────
    # Main Agentic Analysis Workflow
    # ─────────────────────────────────────────────────────────────

    async def analyze_change(self, request: ChangeRequest) -> ImpactReport:
        """Execute the agentic impact analysis orchestration loop.

        The agent understands the change intent, selects and executes tools iteratively,
        computes deterministic impact, verifies evidence, and invokes the LLM for reasoning.
        """
        logger.info(f"=== Starting Agentic Impact Analysis for Repo {request.repo_id} ===")
        logger.info(f"User Request: '{request.query}'")

        report = ImpactReport(
            repo_id=request.repo_id,
            query=request.query,
            status="analyzing",
            created_at=datetime.datetime.now(),
        )

        try:
            # ── Phase 1: Understand Change Request ──
            logger.info("Agent Step 1/8: Understanding change intent...")
            understanding = await self._understand_intent(request)
            target_name = understanding.get("target_component", "")
            report.changed_component = target_name
            report.changed_function = request.target_function or target_name

            # ── Phase 2: Agent Tool Execution Loop — Resolve Target Node ──
            logger.info(f"Agent Step 2/8: Resolving target component '{target_name}' via tools...")
            target_node_id = self._resolve_target_symbol(
                target_name=target_name,
                target_func=request.target_function,
                target_file=request.target_file,
                raw_query=request.query,
            )

            if not target_node_id:
                logger.warning(f"Target component '{target_name}' could not be located.")
                report.status = "completed"
                report.explanation = (
                    f"Target component '{target_name}' could not be identified in the codebase index. "
                    f"Please specify an exact function name, class name, or file path."
                )
                report.risk_level = RiskLevel.LOW
                report.completed_at = datetime.datetime.now()
                return report

            target_node = self.graph.get_node(target_node_id)
            if target_node:
                report.changed_component = target_node.name
                report.changed_file = target_node.file_path
                report.changed_function = target_node.name

            # ── Phase 3: Gather Structural & Dependency Evidence ──
            logger.info(f"Agent Step 3/9: Analyzing dependencies for '{target_node_id}'...")
            dep_data = self.analyze_dependencies(target_node_id)
            for caller in dep_data.get("callers", []):
                report.evidence.append(
                    Evidence(
                        source="code_search",
                        description=f"Caller: {caller.name} ({caller.node_type.value})",
                        file_path=caller.file_path,
                        line_range=f"L{caller.start_line}-{caller.end_line}" if caller.start_line else None,
                        confidence=0.95,
                    )
                )

            # ── Phase 4: Retrieve Semantic RAG Context ──
            logger.info("Agent Step 4/9: Retrieving semantic RAG context...")
            rag_chunks = self.retrieve_rag_context(request.query, k=5)
            if not rag_chunks and target_name:
                rag_chunks = self.retrieve_rag_context(f"{target_name} implementation", k=3)

            for result in rag_chunks[:5]:
                report.evidence.append(
                    Evidence(
                        source="rag_search",
                        description=f"Relevant code: {result.chunk.name} in {result.chunk.file_path}",
                        file_path=result.chunk.file_path,
                        code_snippet=result.chunk.content[:300],
                        confidence=result.score,
                    )
                )

            # ── Phase 5: Traverse Knowledge Graph Neighborhood ──
            logger.info("Agent Step 5/9: Traversing knowledge graph neighborhood...")
            subgraph = self.traverse_knowledge_graph(target_node_id, depth=2)
            if subgraph and subgraph.nodes:
                neighborhood_nodes = [n.name for n in subgraph.nodes if n.id != target_node_id]
                if neighborhood_nodes:
                    report.evidence.append(
                        Evidence(
                            source="graph_analysis",
                            description=f"Knowledge Graph neighborhood contains {len(neighborhood_nodes)} connected entities: {', '.join(neighborhood_nodes[:6])}",
                            confidence=0.90,
                        )
                    )

            # ── Phase 6: Calculate Deterministic Change Impact ──
            logger.info("Agent Step 6/9: Calculating deterministic change impact...")
            impact_data = self.calculate_impact(target_node_id)
            report.affected_files = impact_data["affected_files"]
            report.affected_functions = impact_data["affected_functions"]
            report.dependency_paths = impact_data["dependency_paths"]
            report.api_impacts = impact_data["api_impacts"]
            report.risk_level = impact_data["risk_level"]
            report.risk_score = impact_data["risk_score"]
            report.evidence.extend(impact_data["evidence"])

            # Iterative agent tool fallback if initial impact evidence is low
            iterations = 0
            while len(report.affected_functions) == 0 and iterations < 2:
                iterations += 1
                logger.info(f"Agent Loop Iteration {iterations}: Expanding search via code search & RAG...")
                more_chunks = self.search_code(target_name, limit=10)
                for res in more_chunks:
                    if res.chunk.id != target_node_id and self.graph.get_node(res.chunk.id):
                        extra_impact = self.calculate_impact(res.chunk.id, max_depth=2)
                        if extra_impact["affected_functions"]:
                            report.affected_functions.extend(extra_impact["affected_functions"])
                            report.affected_files.extend(extra_impact["affected_files"])
                            break

            # ── Phase 7: Analyze Test Coverage & Recommendations ──
            logger.info("Agent Step 7/9: Analyzing test impact...")
            affected_for_tests = self.impact_engine.propagate_change(target_node_id)
            test_data = self.find_related_tests(target_node_id, affected_nodes=affected_for_tests)
            report.estimated_test_coverage = test_data.get("coverage", 0.0)
            report.test_recommendations = test_data.get("recommendations", [])

            # ── Phase 8: Multi-Source Verification ──
            logger.info("Agent Step 8/9: Verifying evidence against AST ground truth...")
            report.verification_results = self.verify_results(report)

            # ── Phase 9: LLM Reasoning & Explanation Synthesis ──
            logger.info("Agent Step 9/9: Synthesizing AI explanation with Ollama LLM...")
            report.explanation = await self._generate_reasoning(report)

            report.status = "completed"
            report.completed_at = datetime.datetime.now()
            logger.info(
                f"=== Agentic Impact Analysis Completed ===\n"
                f"  Target: {report.changed_component} ({report.changed_file})\n"
                f"  Risk: {report.risk_level.value.upper()} ({report.risk_score})\n"
                f"  Affected Files: {len(report.affected_files)}\n"
                f"  Affected Functions: {len(report.affected_functions)}\n"
                f"  API Impacts: {len(report.api_impacts)}\n"
                f"  Test Recommendations: {len(report.test_recommendations)}\n"
                f"  Passed Verification: {sum(1 for v in report.verification_results if v.passed)}/{len(report.verification_results)}"
            )
            return report

        except Exception as e:
            logger.error(f"Agent analysis failed: {e}", exc_info=True)
            report.status = "error"
            report.explanation = f"Impact analysis failed: {str(e)}"
            report.completed_at = datetime.datetime.now()
            return report

    # ─────────────────────────────────────────────────────────────
    # AI Assistant QA Capabilities
    # ─────────────────────────────────────────────────────────────

    async def answer_question(
        self,
        question: str,
        repo_name: str = "Repository",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AssistantChatResponse:
        """Answer developer questions regarding the codebase using RAG + Graph + LLM reasoning."""
        logger.info(f"AI Assistant received question: '{question}'")

        # 1. Retrieve RAG chunks
        relevant_chunks = self.retrieve_rag_context(question, k=4)
        if not relevant_chunks:
            # Fallback to symbol search
            symbol_results = self.search_code(question, limit=4)
            relevant_chunks.extend(symbol_results)

        # 2. Build code context
        context_parts = []
        matched_symbols = []
        for i, res in enumerate(relevant_chunks, 1):
            chunk = res.chunk
            if chunk.name:
                matched_symbols.append(chunk.name)
            context_parts.append(
                f"Snippet #{i} ({chunk.chunk_type} `{chunk.name}` in {chunk.file_path}:{chunk.start_line}-{chunk.end_line}):\n"
                f"```{chunk.language}\n{chunk.content[:500]}\n```"
            )
        code_context = "\n\n".join(context_parts) if context_parts else "No specific code chunks matched directly."

        # 3. Build graph context
        graph_info_parts = []
        for sym in matched_symbols[:3]:
            node_matches = self.graph.find_nodes_by_name(sym)
            for node in node_matches[:2]:
                dep_data = self.analyze_dependencies(node.id)
                callers = [c.name for c in dep_data.get("callers", [])[:4]]
                callees = [c.name for c in dep_data.get("callees", [])[:4]]
                graph_info_parts.append(
                    f"- Symbol `{node.name}` in `{node.file_path}`: Callers={callers}, Callees={callees}"
                )
        graph_context = "\n".join(graph_info_parts) if graph_info_parts else "No direct call graph links found."

        # 4. Check if question asks about impact
        impact_context = ""
        if any(w in question.lower() for w in ["impact", "affect", "risk", "breaking", "change"]):
            for sym in matched_symbols[:1]:
                node_matches = self.graph.find_nodes_by_name(sym)
                if node_matches:
                    impact_res = self.calculate_impact(node_matches[0].id)
                    impact_context = (
                        f"Target: {sym} | Risk: {impact_res['risk_level'].value.upper()} | "
                        f"Affected Files: {len(impact_res['affected_files'])} | "
                        f"Affected Functions: {len(impact_res['affected_functions'])}"
                    )

        # 5. Generate LLM prompt
        prompt = build_assistant_prompt(
            question=question,
            repo_name=repo_name,
            code_context=code_context,
            graph_context=graph_context,
            impact_context=impact_context,
        )

        suggested_followups = [
            f"What tests cover {matched_symbols[0]}?" if matched_symbols else "What are the core entry points?",
            f"Show all callers of {matched_symbols[0]}" if matched_symbols else "Explain overall architecture",
            "What happens if this component is refactored?",
        ]

        if await self.llm.is_available() and not isinstance(self.llm, FallbackProvider):
            response_text = await self.llm.generate(prompt, system=SYSTEM_PROMPT)
            if response_text.startswith("[LLM Error:"):
                response_text = self._fallback_assistant_response(question, repo_name, relevant_chunks)
        else:
            response_text = self._fallback_assistant_response(question, repo_name, relevant_chunks)

        return AssistantChatResponse(
            response=response_text,
            relevant_chunks=relevant_chunks,
            suggested_followups=suggested_followups,
        )

    # ─────────────────────────────────────────────────────────────
    # Internal Helpers & Reasoners
    # ─────────────────────────────────────────────────────────────

    async def _understand_intent(self, request: ChangeRequest) -> Dict[str, Any]:
        """Phase 1: Understand change intent using fast heuristic extraction with LLM fallback."""
        if request.target_function:
            return {
                "target_component": request.target_function,
                "change_type": "modification",
                "key_concerns": [],
            }

        # Fast heuristic extraction first to minimize latency
        heuristic = self._heuristic_understanding(request.query)
        if heuristic and heuristic.get("target_component"):
            return heuristic

        if await self.llm.is_available() and not isinstance(self.llm, FallbackProvider):
            prompt = build_understanding_prompt(request.query)
            response = await self.llm.generate(prompt, system=SYSTEM_PROMPT)
            if not response.startswith("[LLM Error:"):
                parsed = self._extract_json(response)
                if parsed and parsed.get("target_component"):
                    return parsed

        return heuristic

    def _resolve_target_symbol(
        self,
        target_name: str,
        target_func: Optional[str],
        target_file: Optional[str],
        raw_query: str,
    ) -> Optional[str]:
        """Resolve the target component to an exact node ID in the knowledge graph."""
        # 1. Exact function match in graph
        if target_func:
            nodes = self.graph.find_nodes_by_name(target_func)
            if nodes:
                return nodes[0].id

        # 2. Search target_name in graph
        if target_name:
            nodes = self.graph.find_nodes_by_name(target_name)
            if nodes:
                for n in nodes:
                    if n.node_type in (NodeType.FUNCTION, NodeType.METHOD):
                        return n.id
                return nodes[0].id

        # 3. Use code search tool
        search_res = self.search_code(target_name or raw_query, limit=5)
        for r in search_res:
            if self.graph.get_node(r.chunk.id):
                return r.chunk.id
            if r.chunk.qualified_name and self.graph.get_node(r.chunk.qualified_name):
                return r.chunk.qualified_name
            nodes = self.graph.find_nodes_by_name(r.chunk.name)
            if nodes:
                return nodes[0].id

        # 4. Use RAG tool
        rag_res = self.retrieve_rag_context(raw_query, k=3)
        for r in rag_res:
            if self.graph.get_node(r.chunk.id):
                return r.chunk.id
            nodes = self.graph.find_nodes_by_name(r.chunk.name)
            if nodes:
                return nodes[0].id

        # 5. Extract keywords from query
        query_words = [w.strip(".,;:\"'()") for w in raw_query.lower().split() if len(w) > 2]
        stop_words = {"change", "chage", "modify", "update", "refactor", "want", "need", "method", "function", "service"}
        for word in query_words:
            if word in stop_words:
                continue
            matched = self.graph.find_nodes_by_name(word)
            if matched:
                return matched[0].id

        return None

    async def _generate_reasoning(self, report: ImpactReport) -> str:
        """Phase 8: Generate grounded LLM reasoning over verified evidence."""
        if not (await self.llm.is_available()) or isinstance(self.llm, FallbackProvider):
            return self._fallback_explanation(report)

        try:
            prompt = build_explanation_prompt(
                query=report.query,
                changed_component=report.changed_component,
                affected_files=report.affected_files,
                affected_functions=report.affected_functions,
                api_impacts=report.api_impacts,
                test_recommendations=report.test_recommendations,
                evidence=report.evidence,
                risk_level=report.risk_level.value,
                risk_score=report.risk_score,
            )
            response = await self.llm.generate(prompt, system=SYSTEM_PROMPT)
            if response and not response.startswith("[LLM Error:"):
                return response
            return self._fallback_explanation(report)
        except Exception as e:
            logger.warning(f"LLM reasoning generation error: {e}")
            return self._fallback_explanation(report)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Safely extract JSON payload from LLM responses."""
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0] if "```" in cleaned else cleaned
                cleaned = cleaned.strip()
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    @staticmethod
    def _heuristic_understanding(query: str) -> Dict[str, Any]:
        """Rule-based extractor when LLM is offline."""
        query_lower = query.lower()
        quoted = re.findall(r'["\'](\w+)["\']', query)
        if quoted:
            return {"target_component": quoted[0], "change_type": "modification", "key_concerns": []}

        action_keywords = ["modify", "change", "chage", "update", "refactor", "fix", "delete", "remove", "add to", "replace"]
        filler = {"the", "a", "an", "this", "that", "in", "to", "for", "with", "from", "method", "function", "class", "service", "file", "logic", "i", "we", "want", "need"}

        for kw in action_keywords:
            if kw in query_lower:
                after = query_lower.split(kw, 1)[1].strip()
                words = [w.strip("().,;:'\"") for w in after.split()]
                for w in words:
                    if w and w not in filler and len(w) > 2:
                        return {"target_component": w, "change_type": "modification", "key_concerns": []}

        words = query.split()
        for w in words:
            clean = w.strip("().,;:'\"").lower()
            if len(clean) > 2 and clean not in filler and clean not in action_keywords:
                return {"target_component": w.strip("().,;:'\""), "change_type": "modification", "key_concerns": []}

        return {"target_component": query[:40], "change_type": "modification", "key_concerns": []}

    @staticmethod
    def _fallback_explanation(report: ImpactReport) -> str:
        """Deterministic rule-based impact explanation when LLM is offline."""
        lines = [
            f"## Impact Analysis: {report.changed_component}",
            "",
            f"**Risk Level:** {report.risk_level.value.upper()} (Score: {report.risk_score:.2f})",
            "",
        ]
        if report.affected_files:
            lines.append(f"**{len(report.affected_files)} Files Affected:**")
            for f in report.affected_files[:10]:
                lines.append(f"- `{f.file_path}` ({f.risk_level.value.upper()} risk)")
            lines.append("")

        if report.affected_functions:
            lines.append(f"**{len(report.affected_functions)} Functions Affected:**")
            for fn in report.affected_functions[:10]:
                lines.append(f"- `{fn.name}` — {fn.impact_type}")
            lines.append("")

        if report.api_impacts:
            lines.append(f"**{len(report.api_impacts)} API Endpoints Affected:**")
            for api in report.api_impacts:
                lines.append(f"- `{api.method} {api.endpoint}`")
            lines.append("")

        if report.test_recommendations:
            lines.append(f"**{len(report.test_recommendations)} Test Recommendations:**")
            for t in report.test_recommendations[:8]:
                lines.append(f"- `{t.test_name}` ({t.priority.value.upper()} priority)")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fallback_assistant_response(
        question: str, repo_name: str, relevant_chunks: List[SearchResult]
    ) -> str:
        """Fallback assistant answer based on static chunk inspection."""
        if not relevant_chunks:
            return (
                f"I analyzed repository **{repo_name}** for *'{question}'*.\n\n"
                f"No matching code entities were found. Try specifying an exact function name, class name, or file path."
            )
        top = relevant_chunks[0].chunk
        files = list(set([r.chunk.file_path.replace("\\", "/") for r in relevant_chunks]))
        return (
            f"### Codebase Context for `{question}`\n\n"
            f"Found **{len(relevant_chunks)} relevant code components** in **{repo_name}**:\n\n"
            f"1. **Primary Component:** `{top.name}` (*{top.chunk_type}*) in `{top.file_path.replace(chr(92), '/')}` (L{top.start_line}–L{top.end_line})\n"
            f"2. **Files Involved:** {', '.join([f'`{f}`' for f in files])}\n\n"
            f"```\n{top.content[:350]}\n```"
        )
