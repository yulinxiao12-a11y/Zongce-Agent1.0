from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OpportunityCreate(BaseModel):
    source_type: str = "notice"
    title: str
    category: str
    dimension: str
    organizer: str = ""
    location: str = ""
    start_time: str = ""
    deadline: str = ""
    season_months: str = ""
    credit_hint: str = ""
    rule_ref: str = ""
    official_url: str = ""
    registration_url: str = ""
    contact_email: str = ""
    article_url: str = ""
    group_qr_url: str = ""
    description: str = ""
    requirements: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    roi_score: float = 3.0


class BasketCreate(BaseModel):
    user_id: int = 1
    opportunity_id: int
    stage: str = "想参加"
    note: str = ""


class BasketUpdate(BaseModel):
    stage: str | None = None
    note: str | None = None


class CertificationCreate(BaseModel):
    user_id: int = 1
    opportunity_id: int | None = None
    title: str
    dimension: str
    award_level: str = ""
    material_manifest: dict[str, Any] = Field(default_factory=dict)
    files: list[dict[str, Any]] = Field(default_factory=list)


class AdminDecision(BaseModel):
    decision: str
    score: float | None = None
    comment: str = ""
    rule_ref: str = ""


class HonorCreate(BaseModel):
    user_id: int = 1
    title: str
    category: str = "证书"
    image_url: str = ""
    visibility: str = "private"


class HonorUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    image_url: str | None = None
    sort_order: int | None = None
    visibility: str | None = None


class ParseOpportunityRequest(BaseModel):
    raw_text: str
