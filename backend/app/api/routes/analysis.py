"""Analysis API routes.

Handles impact analysis requests and report retrieval.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import app_state
from app.db.database import get_db
from app.db.models import Analysis, AnalysisStatus, Repository
from app.models.schemas import (
    AnalysisListResponse,
    AnalysisSummary,
    ChangeRequest,
    ImpactReport,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/impact", response_model=ImpactReport)
async def run_impact_analysis(
    request: ChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a change impact analysis request.

    Executes the 12-step impact analysis pipeline:
    1. Receive request
    2. Understand the goal (LLM)
    3. Search for target code
    4. Find callers
    5. Find related components
    6. RAG retrieval
    7. Find related APIs
    8. Find relevant tests
    9. Impact engine analysis
    10. LLM explanation
    11. Verification
    12. Generate report
    """
    # Verify repository exists and is ready
    repo = await db.get(Repository, request.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status.value != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Repository is not ready (status: {repo.status.value}). "
            f"Please wait for ingestion to complete.",
        )

    # Get the impact agent
    agent = app_state.get_impact_agent(request.repo_id)
    if not agent:
        raise HTTPException(
            status_code=500,
            detail="Impact agent could not be initialized. "
            "The knowledge graph or vector store may not be loaded.",
        )

    # Create analysis record
    analysis = Analysis(
        repo_id=request.repo_id,
        query=request.query,
        status=AnalysisStatus.PENDING,
    )
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)

    # Run the 12-step pipeline
    try:
        analysis.status = AnalysisStatus.ANALYZING
        await db.commit()

        report = await agent.analyze_change(request)

        # Update analysis record
        analysis.status = AnalysisStatus.COMPLETED
        analysis.risk_level = report.risk_level.value
        analysis.risk_score = report.risk_score
        analysis.affected_files_count = len(report.affected_files)
        analysis.affected_functions_count = len(report.affected_functions)
        analysis.report_json = report.model_dump(mode="json")
        analysis.completed_at = datetime.datetime.now()
        await db.commit()

        report.id = analysis.id
        return report

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        analysis.status = AnalysisStatus.ERROR
        analysis.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/history", response_model=AnalysisListResponse)
@router.get("/history/list", response_model=AnalysisListResponse)
async def list_analyses(
    repo_id: Optional[int] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List past analyses, optionally filtered by repository."""
    query = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit)

    if repo_id:
        query = query.where(Analysis.repo_id == repo_id)

    result = await db.execute(query)
    analyses = result.scalars().all()

    summaries = []
    for a in analyses:
        # Get repo name
        repo = await db.get(Repository, a.repo_id)
        summaries.append(
            AnalysisSummary(
                id=a.id,
                repo_id=a.repo_id,
                repo_name=repo.name if repo else "",
                query=a.query,
                status=a.status.value,
                risk_level=a.risk_level,
                risk_score=a.risk_score,
                affected_files_count=a.affected_files_count,
                affected_functions_count=a.affected_functions_count,
                created_at=a.created_at,
                completed_at=a.completed_at,
            )
        )

    return AnalysisListResponse(analyses=summaries, total=len(summaries))


@router.get("/{analysis_id}", response_model=ImpactReport)
async def get_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get analysis results by ID."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if analysis.report_json:
        report = ImpactReport(**analysis.report_json)
        report.id = analysis.id
        return report

    return ImpactReport(
        id=analysis.id,
        repo_id=analysis.repo_id,
        query=analysis.query,
        status=analysis.status.value,
        created_at=analysis.created_at,
    )


@router.get("/{analysis_id}/report", response_model=ImpactReport)
async def get_analysis_report(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the full impact report for an analysis."""
    return await get_analysis(analysis_id, db)
