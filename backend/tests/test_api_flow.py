from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def test_submit_needs_human_before_score_ledger():
    Base.metadata.drop_all(bind=engine)
    client = TestClient(app)
    with client:
        before = client.get("/api/dashboard/summary?user_id=1").json()["data"]["score"]["total"]
        response = client.post(
            "/api/certifications",
            json={
                "user_id": 1,
                "title": "匿名竞赛三等奖认证",
                "dimension": "academic",
                "award_level": "省级三等奖",
                "material_manifest": {"结果证明": True},
            },
        )
        assert response.status_code == 200
        after_submit = client.get("/api/dashboard/summary?user_id=1").json()["data"]["score"]["total"]
        assert after_submit == before

        app_id = response.json()["data"]["id"]
        decision = client.post(
            f"/api/admin/certifications/{app_id}/decision",
            json={"decision": "approved", "score": 6, "comment": "材料补齐后通过"},
        )
        assert decision.status_code == 200
        after_approve = client.get("/api/dashboard/summary?user_id=1").json()["data"]["score"]["total"]
        assert after_approve > before
