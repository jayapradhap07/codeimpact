"""LLM prompt templates for impact analysis reasoning."""

SYSTEM_PROMPT = """You are a senior software architect and AI Impact Analysis Agent.
You analyze software changes using verified evidence from Abstract Syntax Trees (AST),
dependency call graphs, semantic code retrieval, and test impact analysis.

CRITICAL INSTRUCTIONS:
1. ONLY reference files, functions, classes, and dependency paths present in the provided evidence.
2. DO NOT fabricate or invent non-existent components, dependencies, or relations.
3. Clearly explain WHY and HOW downstream components are affected by the proposed change.
4. Highlight architectural risks, regression potentials, and breaking API contracts.
5. Provide concrete, actionable developer recommendations and test execution strategies.
6. Format your response clearly with Markdown headings and bullet points."""


def build_understanding_prompt(query: str) -> str:
    """Build prompt for understanding the change intent."""
    return f"""Analyze the following change request and extract:
1. The target component (function, class, or file) being changed
2. The nature of the change (refactor, bug fix, feature addition, API change, removal)
3. Potential areas of concern

Change request: "{query}"

Respond strictly in JSON format without markdown fences:
{{
    "target_component": "name of the function/class/file",
    "change_type": "refactor|bugfix|feature|api_change|removal",
    "key_concerns": ["concern1", "concern2"]
}}"""


def build_explanation_prompt(
    query: str,
    changed_component: str,
    affected_files: list,
    affected_functions: list,
    api_impacts: list,
    test_recommendations: list,
    evidence: list,
    risk_level: str,
    risk_score: float,
) -> str:
    """Build prompt for generating the impact explanation."""
    affected_files_str = "\n".join(
        f"  - {f.get('file_path', f)} (Risk: {f.get('risk_level', 'unknown')})"
        for f in (affected_files[:15] if isinstance(affected_files[0], dict) else
                  [{"file_path": f.file_path, "risk_level": f.risk_level.value} for f in affected_files[:15]])
    ) if affected_files else "  None identified"

    affected_funcs_str = "\n".join(
        f"  - {f.get('name', f)} ({f.get('impact_type', 'unknown')})"
        for f in (affected_functions[:15] if isinstance(affected_functions[0], dict) else
                  [{"name": f.name, "impact_type": f.impact_type} for f in affected_functions[:15]])
    ) if affected_functions else "  None identified"

    api_str = "\n".join(
        f"  - {a.get('method', '')} {a.get('endpoint', a)}"
        for a in (api_impacts[:5] if isinstance(api_impacts[0], dict) else
                  [{"method": a.method, "endpoint": a.endpoint} for a in api_impacts[:5]])
    ) if api_impacts else "  None affected"

    test_str = "\n".join(
        f"  - {t.get('test_name', t)} (Priority: {t.get('priority', 'unknown')})"
        for t in (test_recommendations[:10] if isinstance(test_recommendations[0], dict) else
                  [{"test_name": t.test_name, "priority": t.priority.value} for t in test_recommendations[:10]])
    ) if test_recommendations else "  No tests found"

    evidence_str = "\n".join(
        f"  - [{e.get('source', 'unknown')}] {e.get('description', e)}"
        for e in (evidence[:10] if isinstance(evidence[0], dict) else
                  [{"source": e.source, "description": e.description} for e in evidence[:10]])
    ) if evidence else "  No evidence collected"

    return f"""Based on the following impact analysis data, provide a clear, detailed explanation
of how the proposed change will affect the codebase.

## Change Request
"{query}"

## Changed Component
{changed_component}

## Risk Assessment
Level: {risk_level.upper()} | Score: {risk_score}

## Affected Files
{affected_files_str}

## Affected Functions
{affected_funcs_str}

## API Endpoints Affected
{api_str}

## Recommended Tests
{test_str}

## Evidence
{evidence_str}

---

Please provide:
1. **Summary**: A concise summary of the change impact (2-3 sentences)
2. **Key Risks**: The most important risks to be aware of
3. **Recommended Actions**: Steps the developer should take before and after making this change
4. **Test Strategy**: Which tests to run and why
5. **Migration Notes**: Any breaking changes or migration steps needed"""


def build_assistant_prompt(
    question: str,
    repo_name: str,
    code_context: str,
    graph_context: str,
    impact_context: str = "",
) -> str:
    """Build prompt for AI Assistant codebase questions."""
    return f"""You are an expert codebase assistant for repository '{repo_name}'.
Answer the user's question accurately using only the verified code context and graph relationships provided below.

## User Question:
{question}

## Verified Code Context:
{code_context if code_context else "No direct matching code snippets found."}

## Knowledge Graph Relationships:
{graph_context if graph_context else "No direct call graph links found."}

{f"## Impact Analysis Context:\n{impact_context}" if impact_context else ""}

Instructions:
- Provide a clear, developer-focused answer.
- Reference specific file names, function names, and line numbers when relevant.
- Do not invent non-existent files or functions.
- If asking about risk or dependencies, explain the exact connection path."""

