"""SQLAlchemy ORM models for the database."""

import datetime
import enum
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class RepoStatus(str, enum.Enum):
    """Repository processing status."""
    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class AnalysisStatus(str, enum.Enum):
    """Analysis processing status."""
    PENDING = "pending"
    UNDERSTANDING = "understanding"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    REASONING = "reasoning"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    ERROR = "error"


class Repository(Base):
    """Repository metadata."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    local_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[RepoStatus] = mapped_column(
        Enum(RepoStatus), default=RepoStatus.PENDING
    )
    languages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    function_count: Mapped[int] = mapped_column(Integer, default=0)
    class_count: Mapped[int] = mapped_column(Integer, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class Analysis(Base):
    """Impact analysis record."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.PENDING
    )
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    affected_files_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_functions_count: Mapped[int] = mapped_column(Integer, default=0)
    report_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="analyses")
