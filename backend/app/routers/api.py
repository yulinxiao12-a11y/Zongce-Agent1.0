from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    CertificationApplication,
    HonorWallItem,
    Opportunity,
    OperationLog,
    PlanBasketItem,
    RuleDocument,
    ScoreLedger,
    User,
)
from app.schemas import (
    AdminDecision,
    BasketCreate,
    BasketUpdate,
    CertificationCreate,
    HonorCreate,
    HonorUpdate,
    OpportunityCreate,
    ParseOpportunityRequest,
)
from app.score_engine import DIMENSIONS, LedgerInput, RULE_VERSION, compute_score
from app.services.ai_client import STRICT_MATERIALS, parse_opportunity, review_certification

router = APIRouter(prefix="/api")


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def model_dict(obj: Any) -> dict[str, Any]:
    data = {col.name: getattr(obj, col.name) for col in obj.__table__.columns}
    for key, value in list(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
    return data


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def add_log(db: Session, actor: str, action: str, target_type: str = "", target_id: int | None = None, detail: str = "") -> None:
    db.add(OperationLog(actor=actor, action=action, target_type=target_type, target_id=target_id, detail=detail))


def serialize_opportunity(item: Opportunity, in_basket: bool = False) -> dict[str, Any]:
    data = model_dict(item)
    data["dimension_label"] = DIMENSIONS.get(item.dimension, {}).get("label", item.dimension)
    data["source_label"] = "近期通知" if item.source_type == "notice" else "常驻备赛"
    data["in_basket"] = in_basket
    return data


@router.get("/health")
def health() -> dict[str, Any]:
    return ok({"status": "ready", "rule_version": RULE_VERSION})


@router.get("/users/demo")
def demo_users(db: Session = Depends(get_db)) -> dict[str, Any]:
    users = db.scalars(select(User).order_by(User.id)).all()
    return ok([model_dict(user) for user in users])


@router.get("/dashboard/summary")
def dashboard_summary(user_id: int = 1, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = get_user(db, user_id)
    ledgers = db.scalars(select(ScoreLedger).where(ScoreLedger.user_id == user.id)).all()
    score = compute_score(
        [
            LedgerInput(
                dimension=item.dimension,
                score=item.score,
                title=item.title,
                duplicate_key=item.duplicate_key,
            )
            for item in ledgers
        ]
    )
    pending = db.scalars(
        select(CertificationApplication).where(
            CertificationApplication.user_id == user.id,
            CertificationApplication.status.in_(["pending_ai", "pending_human", "needs_more"]),
        )
    ).all()
    pending_score = round(sum(item.suggested_score for item in pending), 2)
    ledgers_data = [model_dict(item) for item in ledgers]
    return ok(
        {
            "user": model_dict(user),
            "score": score,
            "pending_score": pending_score,
            "goal_gap": max(0, round(90 - score["total"], 2)),
            "ledgers": ledgers_data,
            "pending_applications": [model_dict(item) for item in pending],
        }
    )


@router.get("/opportunities")
def list_opportunities(
    user_id: int = 1,
    source_type: str | None = None,
    category: str | None = None,
    dimension: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(Opportunity).order_by(Opportunity.source_type.desc(), Opportunity.roi_score.desc(), Opportunity.id)
    if source_type:
        query = query.where(Opportunity.source_type == source_type)
    if category:
        query = query.where(Opportunity.category == category)
    if dimension:
        query = query.where(Opportunity.dimension == dimension)
    if keyword:
        query = query.where(Opportunity.title.contains(keyword.strip()))
    items = db.scalars(query).all()
    basket_ids = set(
        db.scalars(select(PlanBasketItem.opportunity_id).where(PlanBasketItem.user_id == user_id)).all()
    )
    return ok([serialize_opportunity(item, item.id in basket_ids) for item in items])


@router.get("/opportunities/{opportunity_id}")
def opportunity_detail(opportunity_id: int, user_id: int = 1, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Opportunity, opportunity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="机会不存在")
    in_basket = db.scalar(
        select(PlanBasketItem.id).where(
            PlanBasketItem.user_id == user_id,
            PlanBasketItem.opportunity_id == opportunity_id,
        )
    )
    return ok(serialize_opportunity(item, bool(in_basket)))


@router.post("/opportunities")
def create_opportunity(body: OpportunityCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = Opportunity(**body.model_dump())
    db.add(item)
    db.flush()
    add_log(db, "王五", "发布活动/比赛", "opportunity", item.id, item.title)
    db.commit()
    db.refresh(item)
    return ok(serialize_opportunity(item), "已发布")


@router.post("/ai/parse-opportunity")
async def parse_opportunity_api(body: ParseOpportunityRequest) -> dict[str, Any]:
    result = await parse_opportunity(body.raw_text)
    return ok(result)


@router.get("/plan-basket")
def list_basket(user_id: int = 1, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(
        select(PlanBasketItem)
        .options(joinedload(PlanBasketItem.opportunity))
        .where(PlanBasketItem.user_id == user_id)
        .order_by(PlanBasketItem.created_at.desc())
    ).all()
    data = []
    for item in items:
        row = model_dict(item)
        row["opportunity"] = serialize_opportunity(item.opportunity)
        data.append(row)
    return ok(data)


@router.post("/plan-basket")
def add_basket(body: BasketCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_user(db, body.user_id)
    if db.get(Opportunity, body.opportunity_id) is None:
        raise HTTPException(status_code=404, detail="机会不存在")
    existing = db.scalar(
        select(PlanBasketItem).where(
            PlanBasketItem.user_id == body.user_id,
            PlanBasketItem.opportunity_id == body.opportunity_id,
        )
    )
    if existing:
        return ok(model_dict(existing), "已在备赛清单")
    item = PlanBasketItem(**body.model_dump())
    db.add(item)
    db.flush()
    add_log(db, "张三", "加入备赛清单", "plan_basket", item.id, str(body.opportunity_id))
    db.commit()
    db.refresh(item)
    return ok(model_dict(item), "已加入备赛清单")


@router.patch("/plan-basket/{item_id}")
def update_basket(item_id: int, body: BasketUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(PlanBasketItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="清单条目不存在")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)
    add_log(db, "张三", "更新备赛状态", "plan_basket", item.id, str(updates))
    db.commit()
    db.refresh(item)
    return ok(model_dict(item))


@router.delete("/plan-basket/{item_id}")
def delete_basket(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(PlanBasketItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="清单条目不存在")
    db.delete(item)
    add_log(db, "张三", "移出备赛清单", "plan_basket", item_id)
    db.commit()
    return ok({"id": item_id}, "已移出")


@router.get("/material-templates")
def material_templates(db: Session = Depends(get_db)) -> dict[str, Any]:
    active_rule_doc = db.scalar(select(RuleDocument).where(RuleDocument.is_active == 1).order_by(RuleDocument.uploaded_at.desc()))
    active_rule = model_dict(active_rule_doc) if active_rule_doc else None
    return ok(
        {
            "rule_version": RULE_VERSION,
            "active_rule_document": active_rule,
            "strict_materials": STRICT_MATERIALS,
            "dimensions": [
                {"key": key, **value}
                for key, value in DIMENSIONS.items()
            ],
            "notes": [
                "AI 初审不代表最终通过，人工审核通过后才写入 ScoreLedger。",
                "同一比赛或成果多次获奖，计算时只取最高分。",
                "自行参加且无学校/学院通知支撑的比赛，默认进入存疑复核。",
            ],
        }
    )


@router.get("/rule-documents")
def list_rule_documents(db: Session = Depends(get_db)) -> dict[str, Any]:
    docs = db.scalars(select(RuleDocument).order_by(RuleDocument.is_active.desc(), RuleDocument.uploaded_at.desc())).all()
    return ok([model_dict(doc) for doc in docs])


@router.post("/rule-documents/upload")
async def upload_rule_document(
    file: UploadFile = File(...),
    version: str = Form("2024-07-12-electronic-info-v1"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".doc", ".docx"}:
        raise HTTPException(status_code=400, detail="Only pdf/doc/docx rule documents are supported")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Rule document cannot exceed 20MB")

    upload_dir = Path(settings.upload_dir) / "rules"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid4().hex}{suffix}"
    target = upload_dir / safe_name
    target.write_bytes(content)

    for doc in db.scalars(select(RuleDocument).where(RuleDocument.is_active == 1)).all():
        doc.is_active = 0
    rule_doc = RuleDocument(
        name=file.filename or "rule-document",
        version=version,
        file_url=f"/uploads/rules/{safe_name}",
        notes=notes,
        is_active=1,
    )
    db.add(rule_doc)
    db.flush()
    add_log(db, "王五", "上传并启用综测细则", "rule_document", rule_doc.id, rule_doc.name)
    db.commit()
    db.refresh(rule_doc)
    return ok(model_dict(rule_doc), "Rule document uploaded")


@router.post("/rule-documents/{document_id}/activate")
def activate_rule_document(document_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    target = db.get(RuleDocument, document_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Rule document not found")
    for doc in db.scalars(select(RuleDocument)).all():
        doc.is_active = 1 if doc.id == document_id else 0
    add_log(db, "王五", "切换当前综测细则", "rule_document", target.id, target.name)
    db.commit()
    db.refresh(target)
    return ok(model_dict(target), "Rule document activated")


@router.post("/certifications")
async def create_certification(body: CertificationCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_user(db, body.user_id)
    if body.opportunity_id and db.get(Opportunity, body.opportunity_id) is None:
        raise HTTPException(status_code=404, detail="机会不存在")
    app = CertificationApplication(**body.model_dump())
    db.add(app)
    db.flush()

    ai = await review_certification(app.material_manifest, app.title, app.dimension, app.award_level)
    app.ai_review = ai
    app.ai_confidence = float(ai.get("confidence", 0))
    app.risk_tags = list(ai.get("risk_tags", []))
    app.suggested_score = float(ai.get("suggested_score", 0) or 0)
    app.status = "pending_human"
    if ai.get("missing_materials"):
        app.status = "needs_more"
    add_log(db, "张三", "提交综测认证", "certification", app.id, app.title)
    db.commit()
    db.refresh(app)
    return ok(model_dict(app), "已提交，等待管理端人工审核")


@router.post("/certifications/{application_id}/ai-review")
async def rerun_ai_review(application_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    app = db.get(CertificationApplication, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    ai = await review_certification(app.material_manifest, app.title, app.dimension, app.award_level)
    app.ai_review = ai
    app.ai_confidence = float(ai.get("confidence", 0))
    app.risk_tags = list(ai.get("risk_tags", []))
    app.suggested_score = float(ai.get("suggested_score", app.suggested_score) or 0)
    app.status = "pending_human" if not ai.get("missing_materials") else "needs_more"
    add_log(db, "王五", "重新运行AI初审", "certification", app.id)
    db.commit()
    db.refresh(app)
    return ok(model_dict(app))


@router.get("/certifications")
def list_certifications(
    user_id: int | None = Query(default=1),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(CertificationApplication).options(joinedload(CertificationApplication.opportunity)).order_by(CertificationApplication.created_at.desc())
    if user_id:
        query = query.where(CertificationApplication.user_id == user_id)
    if status:
        query = query.where(CertificationApplication.status == status)
    apps = db.scalars(query).all()
    data = []
    for app in apps:
        row = model_dict(app)
        row["opportunity_title"] = app.opportunity.title if app.opportunity else ""
        data.append(row)
    return ok(data)


@router.get("/admin/certifications")
def admin_certifications(
    queue: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(CertificationApplication).options(joinedload(CertificationApplication.user), joinedload(CertificationApplication.opportunity))
    if queue == "high_confidence":
        query = query.where(CertificationApplication.ai_confidence >= 0.85, CertificationApplication.status == "pending_human")
    elif queue == "needs_more":
        query = query.where(CertificationApplication.status == "needs_more")
    elif queue == "risk":
        query = query.where((CertificationApplication.status == "needs_more") | (CertificationApplication.ai_confidence < 0.7))
    elif queue:
        query = query.where(CertificationApplication.status == queue)
    apps = db.scalars(query.order_by(CertificationApplication.created_at.desc())).all()
    data = []
    for app in apps:
        row = model_dict(app)
        row["student_name"] = app.user.name
        row["opportunity_title"] = app.opportunity.title if app.opportunity else ""
        data.append(row)
    return ok(data)


@router.post("/admin/certifications/{application_id}/decision")
def admin_decision(application_id: int, body: AdminDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    app = db.get(CertificationApplication, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="申请不存在")

    if body.decision not in {"approved", "rejected", "needs_more"}:
        raise HTTPException(status_code=400, detail="无效审核决定")

    app.status = body.decision
    app.admin_comment = body.comment
    if body.decision == "approved":
        score = body.score if body.score is not None else app.suggested_score
        if score <= 0:
            raise HTTPException(status_code=400, detail="通过时加分必须大于 0")
        existing = db.scalar(select(ScoreLedger).where(ScoreLedger.application_id == app.id))
        if existing is None:
            ledger = ScoreLedger(
                user_id=app.user_id,
                application_id=app.id,
                dimension=app.dimension,
                title=app.title,
                score=score,
                rule_ref=body.rule_ref or app.ai_review.get("rule_ref", ""),
                duplicate_key=app.title.split("认证")[0].strip() or app.title,
            )
            db.add(ledger)
    add_log(db, "王五", f"人工审核{body.decision}", "certification", app.id, body.comment)
    db.commit()
    db.refresh(app)
    return ok(model_dict(app), "审核结果已保存")


@router.get("/honor-wall")
def list_honors(user_id: int = 1, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(
        select(HonorWallItem).where(HonorWallItem.user_id == user_id).order_by(HonorWallItem.sort_order, HonorWallItem.id)
    ).all()
    return ok([model_dict(item) for item in items])


@router.post("/honor-wall")
def create_honor(body: HonorCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    max_order = db.scalar(select(func.max(HonorWallItem.sort_order)).where(HonorWallItem.user_id == body.user_id)) or 0
    item = HonorWallItem(**body.model_dump(), sort_order=max_order + 1)
    db.add(item)
    db.flush()
    add_log(db, "张三", "新增荣誉墙", "honor", item.id, item.title)
    db.commit()
    db.refresh(item)
    return ok(model_dict(item), "已加入荣誉星墙")


@router.patch("/honor-wall/{item_id}")
def update_honor(item_id: int, body: HonorUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(HonorWallItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="荣誉项不存在")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    add_log(db, "张三", "更新荣誉墙", "honor", item.id)
    db.commit()
    db.refresh(item)
    return ok(model_dict(item))


@router.delete("/honor-wall/{item_id}")
def delete_honor(item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(HonorWallItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="荣誉项不存在")
    db.delete(item)
    add_log(db, "张三", "删除荣誉墙", "honor", item_id)
    db.commit()
    return ok({"id": item_id})


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".doc", ".docx"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp/pdf/doc/docx")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    target = upload_dir / filename
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过 10MB")
    target.write_bytes(content)
    return ok({"filename": filename, "url": f"/uploads/{filename}"})


@router.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    app_count = db.scalar(select(func.count(CertificationApplication.id))) or 0
    pending_count = db.scalar(
        select(func.count(CertificationApplication.id)).where(
            CertificationApplication.status.in_(["pending_ai", "pending_human", "needs_more"])
        )
    ) or 0
    opportunity_count = db.scalar(select(func.count(Opportunity.id))) or 0
    approved_score = db.scalar(select(func.sum(ScoreLedger.score))) or 0
    logs = db.scalars(select(OperationLog).order_by(OperationLog.created_at.desc()).limit(8)).all()
    return ok(
        {
            "application_count": app_count,
            "pending_count": pending_count,
            "opportunity_count": opportunity_count,
            "approved_score": round(float(approved_score), 2),
            "logs": [model_dict(item) for item in logs],
        }
    )
