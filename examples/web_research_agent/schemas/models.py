from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None


class Metric(BaseModel):
    name: str
    value: Optional[str] = None
    context: Optional[str] = None


class ExtractedInsight(BaseModel):
    url: str
    title: Optional[str] = None
    summary: str
    main_points: List[str] = Field(default_factory=list)
    metrics: List[Metric] = Field(default_factory=list)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    quotes: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    error: Optional[str] = None


class ConsolidatedFinding(BaseModel):
    statement: str
    evidence_urls: List[str] = Field(default_factory=list)
    agreement_level: Optional[str] = None
    priority: Optional[str] = None
    conflicts: List[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    topic: str
    findings: List[ConsolidatedFinding] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    sources: List[str] = Field(default_factory=list)
    followups: List[str] = Field(default_factory=list)


__all__ = [
    "SearchResult",
    "Metric",
    "ExtractedInsight",
    "ConsolidatedFinding",
    "FinalReport",
]
