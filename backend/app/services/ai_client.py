from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


STRICT_MATERIALS = [
    "活动或比赛通知",
    "参赛或参与证明",
    "结果证明",
    "官方来源证明",
    "个人身份匹配证明",
]


def _fallback_review(material_manifest: dict[str, Any], title: str, dimension: str) -> dict[str, Any]:
    missing = [name for name in STRICT_MATERIALS if not material_manifest.get(name)]
    confidence = 0.35 if missing else 0.68
    risk_tags = ["AI未配置", "需人工复核"]
    if missing:
        risk_tags.append("材料缺失")
    return {
        "recognized_text": f"已收到《{title}》材料清单，当前环境未配置 AI_API_KEY，未调用外部模型。",
        "missing_materials": missing,
        "rule_ref": "电子与信息学院综测细则：学业/德育/文体附加分需按通知来源与获奖级别人工核验",
        "suggested_dimension": dimension,
        "suggested_score": 0 if missing else 1,
        "confidence": confidence,
        "risk_tags": risk_tags,
        "recommendation": "不建议自动通过；请管理端按原始材料二次审核。",
        "configured": False,
    }


async def _chat_json(messages: list[dict[str, Any]], model: str) -> dict[str, Any]:
    if not settings.ai_api_key:
        raise RuntimeError("AI_API_KEY is not configured")

    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


async def review_certification(material_manifest: dict[str, Any], title: str, dimension: str, award_level: str) -> dict[str, Any]:
    if not settings.ai_api_key:
        return _fallback_review(material_manifest, title, dimension)

    system = (
        "你是电子与信息学院综测材料初审智能体。你只能做初审建议，不能直接通过。"
        "审核必须严格：至少检查活动或比赛通知、参赛或参与证明、结果证明、官方来源证明、个人身份匹配证明。"
        "按电子与信息学院综测细则判断可能归属德育、学业或文体，并输出 JSON。"
    )
    user = {
        "title": title,
        "dimension": dimension,
        "award_level": award_level,
        "required_materials": STRICT_MATERIALS,
        "material_manifest": material_manifest,
        "output_schema": {
            "recognized_text": "string",
            "missing_materials": ["string"],
            "rule_ref": "string",
            "suggested_dimension": "moral|academic|arts_sports",
            "suggested_score": "number",
            "confidence": "0-1 number",
            "risk_tags": ["string"],
            "recommendation": "string",
        },
    }
    result = await _chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        settings.ai_text_model,
    )
    result.setdefault("missing_materials", [])
    result.setdefault("risk_tags", [])
    result.setdefault("confidence", 0.5)
    result.setdefault("suggested_score", 0)
    result["configured"] = True
    return result


async def parse_opportunity(raw_text: str) -> dict[str, Any]:
    if not settings.ai_api_key:
        return {
            "title": raw_text.strip().splitlines()[0][:60] if raw_text.strip() else "未命名通知",
            "category": "活动通知",
            "dimension": "moral",
            "deadline": "",
            "location": "",
            "description": raw_text.strip(),
            "confidence": 0.3,
            "configured": False,
        }

    system = "你是校园活动通知结构化助手。提取活动标题、类别、综测归属、时间地点、报名方式和材料要求，返回 JSON。"
    result = await _chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": raw_text},
        ],
        settings.ai_text_model,
    )
    result["configured"] = True
    return result
