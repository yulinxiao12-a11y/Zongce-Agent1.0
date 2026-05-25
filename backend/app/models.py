from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    college: Mapped[str] = mapped_column(String(80), default="电子与信息学院")
    major: Mapped[str] = mapped_column(String(80), default="电子信息工程")

    basket_items: Mapped[list[PlanBasketItem]] = relationship(back_populates="user")
    applications: Mapped[list[CertificationApplication]] = relationship(back_populates="user")
    ledgers: Mapped[list[ScoreLedger]] = relationship(back_populates="user")
    honors: Mapped[list[HonorWallItem]] = relationship(back_populates="user")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # notice / evergreen
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    organizer: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    start_time: Mapped[str] = mapped_column(String(40), default="")
    deadline: Mapped[str] = mapped_column(String(40), default="")
    season_months: Mapped[str] = mapped_column(String(80), default="")
    credit_hint: Mapped[str] = mapped_column(String(240), default="")
    rule_ref: Mapped[str] = mapped_column(String(160), default="")
    official_url: Mapped[str] = mapped_column(String(500), default="")
    registration_url: Mapped[str] = mapped_column(String(500), default="")
    contact_email: Mapped[str] = mapped_column(String(120), default="")
    article_url: Mapped[str] = mapped_column(String(500), default="")
    group_qr_url: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    images: Mapped[list[str]] = mapped_column(JSON, default=list)
    roi_score: Mapped[float] = mapped_column(Float, default=3.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    basket_items: Mapped[list[PlanBasketItem]] = relationship(back_populates="opportunity")
    applications: Mapped[list[CertificationApplication]] = relationship(back_populates="opportunity")


class PlanBasketItem(Base):
    __tablename__ = "plan_basket_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), default="想参加")
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="basket_items")
    opportunity: Mapped[Opportunity] = relationship(back_populates="basket_items")


class CertificationApplication(Base):
    __tablename__ = "certification_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    award_level: Mapped[str] = mapped_column(String(80), default="")
    material_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ai_review: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ai_confidence: Mapped[float] = mapped_column(Float, default=0)
    risk_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    suggested_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending_ai")
    admin_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    user: Mapped[User] = relationship(back_populates="applications")
    opportunity: Mapped[Opportunity | None] = relationship(back_populates="applications")


class ScoreLedger(Base):
    __tablename__ = "score_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("certification_applications.id"), nullable=True)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_ref: Mapped[str] = mapped_column(String(180), default="")
    duplicate_key: Mapped[str] = mapped_column(String(180), default="")
    approved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="ledgers")


class HonorWallItem(Base):
    __tablename__ = "honor_wall_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="证书")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="honors")


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), default="")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class RuleDocument(Base):
    __tablename__ = "rule_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[str] = mapped_column(String(80), default="")
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
