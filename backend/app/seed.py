from __future__ import annotations

from pathlib import Path
from shutil import copyfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CertificationApplication,
    HonorWallItem,
    Opportunity,
    PlanBasketItem,
    RuleDocument,
    ScoreLedger,
    User,
)


def seed_demo_data(db: Session) -> None:
    seed_rule_document(db)
    if db.scalar(select(User.id).limit(1)):
        seed_notice_opportunities(db)
        strip_demo_links(db)
        seed_score_ledgers(db)
        seed_audit_showcase(db)
        seed_honor_showcase(db)
        return

    users = [
        User(id=1, name="张三", role="student"),
        User(id=2, name="李四", role="student"),
        User(id=3, name="王五", role="admin"),
    ]
    db.add_all(users)

    opportunities = [
        Opportunity(
            source_type="notice",
            title="智创未来 AI 赋能校园智能体应用开发大赛",
            category="学科竞赛",
            dimension="academic",
            organizer="科研处、研究生院、教务处、团委、网络信息中心",
            location="白云校区图书馆讲学厅",
            start_time="2026-05-24",
            deadline="2026-05-23 23:59",
            credit_hint="校级学科竞赛，获奖后按学业竞赛规则人工核验。",
            rule_ref="学业附加分：其他各类竞赛校级一等奖5、二等奖4、三等奖3、其他2；重点科技竞赛另按细则核定。",
            registration_url="",
            contact_email="",
            article_url="",
            description="围绕校园真实应用场景开发智能体应用，提交设计文档与演示视频。演示数据已匿名化。",
            requirements=["队长报名", "提交 PDF 作品文档", "提交 5 分钟内演示视频", "加入通知群"],
            attachments=[{"name": "作品报告模板.doc", "url": "/static/template.doc"}],
            tags=["AI", "校园服务", "校级"],
            roi_score=4.5,
        ),
        Opportunity(
            source_type="notice",
            title="学院志愿服务与义务劳动招募",
            category="志愿公益",
            dimension="moral",
            organizer="电子与信息学院",
            location="白云校区",
            start_time="2026-05-28",
            deadline="2026-05-25 18:00",
            credit_hint="志愿活动按 4 小时 1 分，最高 12 分；负责学生干部折半。",
            rule_ref="德育附加分：志愿活动、义务劳动、公益活动一次1分，按小时算4小时1分，总计最高12分。",
            registration_url="",
            description="需按时签到签退，活动结束后由组织方提供参与证明。",
            requirements=["报名表", "签到记录", "活动时长证明"],
            tags=["志愿", "德育", "低门槛"],
            roi_score=4.0,
        ),
        *[
            Opportunity(
                source_type="evergreen",
                title=title,
                category=category,
                dimension=dimension,
                organizer=organizer,
                season_months=season,
                credit_hint=hint,
                rule_ref=rule,
                official_url=url,
                description=desc,
                requirements=["官方通知", "报名或参赛名单", "获奖或结果证明", "个人身份匹配证明"],
                tags=tags,
                roi_score=score,
            )
            for title, category, dimension, organizer, season, hint, rule, url, desc, tags, score in [
                ("全国大学生电子设计竞赛", "重点科技竞赛", "academic", "全国大学生电子设计竞赛组委会", "通常 7-8 月", "电子信息专业高度相关，获奖后可能按重点科技竞赛核验。", "学业附加分：重点科技竞赛，省级三等奖15分、国家级按细则核定。", "https://nuedc.xjtu.edu.cn/", "面向电子信息类学生的综合硬件设计竞赛，强调电路、控制、测试与工程实现。", ["电子", "硬件", "重点竞赛"], 5.0),
                ("蓝桥杯全国软件和信息技术专业人才大赛", "学科竞赛", "academic", "蓝桥杯大赛组委会", "通常 3-6 月", "程序设计、电子、嵌入式等方向，获奖需结合学院通知核验。", "学业附加分：其他各类竞赛，国家/省/校级按获奖等级核定。", "https://dasai.lanqiao.cn/", "包含软件、电子、视觉艺术等赛道，适合作为长期备赛项目。", ["编程", "电子", "省赛"], 4.6),
                ("中国大学生计算机设计大赛", "学科竞赛", "academic", "中国大学生计算机设计大赛组委会", "通常 3-8 月", "适合软件作品、AI 应用、数字媒体等方向。", "学业附加分：其他各类竞赛，专业相关加在学业。", "https://jsjds.blcu.edu.cn/", "以计算机应用设计为核心，适合把课程项目继续打磨参赛。", ["软件", "AI", "作品赛"], 4.2),
                ("全国大学生数学建模竞赛", "学科竞赛", "academic", "全国大学生数学建模竞赛组委会", "通常 9 月", "建模能力与论文写作要求高，电子信息专业可参与。", "学业附加分：其他各类竞赛，按级别和奖项核定。", "https://www.mcm.edu.cn/index.moma", "三人组队完成建模、求解、论文撰写，适合提升科研表达能力。", ["数学建模", "论文", "团队"], 4.4),
                ("全国大学生嵌入式芯片与系统设计竞赛", "重点科技竞赛", "academic", "嵌入式芯片与系统设计竞赛组委会", "通常 3-8 月", "与电子信息工程强相关，适合单片机、嵌入式、AIoT 方向。", "学业附加分：重点科技竞赛或其他专业竞赛，按学院认定核验。", "https://www.socchina.net/", "围绕芯片、嵌入式系统和应用创新进行作品开发。", ["嵌入式", "芯片", "AIoT"], 4.7),
                ("全国大学生集成电路创新创业大赛", "重点科技竞赛", "academic", "集创赛组委会", "通常 1-8 月", "适合芯片、EDA、数字电路、模拟电路相关方向。", "学业附加分：专业相关竞赛，具体加分以学院通知和获奖证明为准。", "https://univ.ciciec.com/", "面向集成电路方向的创新实践赛事，适合电子类学生长期准备。", ["集成电路", "EDA", "创新"], 4.3),
                ("全国大学生物联网设计竞赛", "学科竞赛", "academic", "全国大学生物联网设计竞赛组委会", "通常 3-8 月", "适合传感、通信、嵌入式、云平台综合项目。", "学业附加分：其他各类竞赛，专业相关加在学业。", "https://iot.sjtu.edu.cn/", "围绕物联网系统设计与应用创新展开，适合电子信息工程专业。", ["物联网", "传感器", "工程"], 4.2),
                ("全国大学生智能汽车竞赛", "重点科技竞赛", "academic", "全国大学生智能汽车竞赛组委会", "通常 3-8 月", "硬件、控制、算法综合要求高，适合电子与自动化方向。", "学业附加分：重点科技竞赛或其他专业竞赛，按学院认定核验。", "https://www.smartcarrace.com/", "以智能车设计、调试和竞速为核心的工程实践赛事。", ["智能车", "控制", "硬件"], 4.5),
                ("RoboMaster 机甲大师高校系列赛", "重点科技竞赛", "academic", "RoboMaster 组委会", "通常全年分阶段", "适合机械、电子、控制、视觉算法协作。", "学业附加分：专业相关竞赛，需学校/学院通知与参赛证明。", "https://www.robomaster.com/zh-CN", "大型机器人竞技与工程项目，适合团队长期建设。", ["机器人", "视觉", "团队"], 4.0),
                ("华为 ICT 大赛", "学科竞赛", "academic", "华为 ICT Academy", "通常 9 月至次年 5 月", "网络、云、AI、计算方向均可备赛，证书与竞赛需分别核验。", "学业附加分：竞赛或专业技术等级证书按细则核定。", "https://e.huawei.com/cn/talent/ict-academy/#/ict-contest", "面向 ICT 技术能力的竞赛，适合网络、云计算、AI 方向。", ["ICT", "云", "AI"], 3.9),
                ("全国大学生信息安全竞赛", "学科竞赛", "academic", "全国大学生信息安全竞赛组委会", "通常 4-8 月", "适合网络安全、密码、系统安全、攻防实践方向。", "学业附加分：专业相关竞赛，按级别和奖项核定。", "https://www.ciscn.cn/", "面向信息安全作品和创新实践的全国性赛事。", ["信息安全", "网络", "攻防"], 4.1),
                ("中国国际大学生创新大赛", "创新创业", "academic", "教育部等", "通常 4-10 月", "创新创业类重点赛事，需重点核验参赛角色与获奖级别。", "学业附加分：重点科技竞赛互联网+按细则核定。", "https://cy.ncss.cn/", "围绕创新创业项目进行商业计划、路演和项目实践。", ["创新创业", "路演", "重点竞赛"], 4.6),
                ("挑战杯系列竞赛", "创新创业", "academic", "共青团中央等", "通常按大挑/小挑周期", "大挑、小挑均属于重点关注竞赛，需按具体通知核验。", "学业附加分：重点科技竞赛大挑、小挑按细则核定。", "https://tiaozhanbei.net/", "包含课外学术科技作品竞赛和创业计划竞赛。", ["大挑", "小挑", "科创"], 4.6),
                ("大学生创新创业训练计划项目", "科研项目", "academic", "教育部/学校教务部门", "通常春季申报", "立项、结项分别核验，负责人和成员比例不同。", "学业附加分：大创立项/结项按国家级、省级、校级及成员排名核定。", "https://gjcxcy.bjtu.edu.cn/", "面向本科生科研训练和创新创业实践，适合作为长期项目。", ["大创", "科研", "项目"], 4.4),
            ]
        ],
    ]
    db.add_all(opportunities)
    db.flush()

    db.add_all(
        [
            PlanBasketItem(user_id=1, opportunity_id=3, stage="备赛中", note="先刷历年题，6 月前组队。"),
            PlanBasketItem(user_id=1, opportunity_id=4, stage="想参加", note="关注学院是否转发通知。"),
        ]
    )
    db.add_all(
        [
            CertificationApplication(
                user_id=1,
                opportunity_id=4,
                title="蓝桥杯省级三等奖认证",
                dimension="academic",
                award_level="省级三等奖",
                material_manifest={"结果证明": True, "个人身份匹配证明": True},
                ai_review={
                    "recognized_text": "检测到获奖证明，但缺少官方通知与参赛名单。",
                    "missing_materials": ["活动或比赛通知", "参赛或参与证明", "官方来源证明"],
                    "rule_ref": "其他各类竞赛省级三等奖可参考 6 分，需人工核验。",
                    "recommendation": "要求补材料",
                },
                ai_confidence=0.46,
                risk_tags=["材料缺失", "需人工复核"],
                suggested_score=6,
                status="needs_more",
                admin_comment="请补充学校或学院转发通知、参赛名单截图。",
            )
        ]
    )
    db.commit()
    seed_notice_opportunities(db)
    strip_demo_links(db)
    seed_score_ledgers(db)
    seed_audit_showcase(db)
    seed_honor_showcase(db)


def strip_demo_links(db: Session) -> None:
    for item in db.scalars(select(Opportunity)).all():
        for field in ("official_url", "registration_url", "article_url"):
            value = getattr(item, field) or ""
            if "example.edu" in value or value == "https://mp.weixin.qq.com/":
                setattr(item, field, "")
        if "example." in (item.contact_email or ""):
            item.contact_email = ""
    db.commit()


def seed_rule_document(db: Session) -> None:
    if db.scalar(select(RuleDocument.id).limit(1)):
        return
    source = Path.cwd().parent / "2025年7月电信学院综测细则（公示版）(1).docx"
    upload_dir = Path("uploads") / "rules"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / "current-zongce-rules.docx"
    if source.exists() and not target.exists():
        copyfile(source, target)
    db.add(
        RuleDocument(
            name="2025年7月电信学院综测细则（公示版）",
            version="2024-07-12-electronic-info-v1",
            file_url="/uploads/rules/current-zongce-rules.docx",
            notes="系统当前用于计算与审核提示的综测细则，可在管理端上传新版本并切换。",
            is_active=1,
        )
    )
    db.commit()


def seed_notice_opportunities(db: Session) -> None:
    demo_base = "/uploads/opportunity-demo"
    notices = [
        {
            "source_type": "notice",
            "title": "电信学院院办值班人员补招",
            "category": "院务助理",
            "dimension": "moral",
            "organizer": "电子与信息学院综合事务部",
            "location": "白云校区学院办公室",
            "start_time": "2026-05-25 起，每周一次",
            "deadline": "2026-06-20 20:00",
            "credit_hint": "可作为学院工作与综合素质经历，是否加分以学院证明和综测细则审核为准。",
            "rule_ref": "德育附加分：学院组织的服务、劳动、学生工作经历按证明材料人工核验。",
            "registration_url": "",
            "contact_email": "",
            "article_url": "",
            "group_qr_url": f"{demo_base}/office-duty-cover.jpg",
            "description": "参考活动素材整理：协助老师处理办公室日常事务，每周一次，每次两节课。演示版已将报名截止延后。",
            "requirements": ["报名表", "排班确认", "工作记录", "学院证明", "个人身份匹配证明"],
            "attachments": [],
            "images": [f"{demo_base}/office-duty-cover.jpg"],
            "tags": ["学院工作", "德育", "院办值班"],
            "roi_score": 4.1,
        },
        {
            "source_type": "notice",
            "title": "白云校区学生处学生助理招新",
            "category": "学生工作",
            "dimension": "moral",
            "organizer": "学生处",
            "location": "白云校区学生处",
            "start_time": "2026-06-01 起",
            "deadline": "2026-06-25 20:00",
            "credit_hint": "学生助理经历可作为综合素质材料，需提交招募通知、报名表、录用或工作证明。",
            "rule_ref": "德育附加分：学生工作、志愿服务或义务劳动按学院证明材料人工核验。",
            "registration_url": "",
            "contact_email": "",
            "group_qr_url": f"{demo_base}/student-office-qr.jpg",
            "description": "参考活动素材整理：面向白云校区在校学生招募学生助理，协助二级学院事务、大型活动和临时工作。",
            "requirements": ["报名表", "录用通知", "工作时长证明", "组织方证明", "个人身份匹配证明"],
            "attachments": [{"name": "学生处招新报名表.docx", "url": f"{demo_base}/student-office-form.docx"}],
            "images": [f"{demo_base}/student-office-qr.jpg"],
            "tags": ["学生助理", "报名表", "德育"],
            "roi_score": 4.0,
        },
        {
            "source_type": "notice",
            "title": "粤风赓续·文脉兴湾诗歌节知识竞赛观众招募",
            "category": "文化活动",
            "dimension": "arts_sports",
            "organizer": "易班发展中心",
            "location": "广州校区学术报告厅",
            "start_time": "2026-06-12 19:00",
            "deadline": "2026-06-10 18:30",
            "credit_hint": "文化艺术类活动可作为文体材料，需以活动签到、主办方证明和综测细则核验。",
            "rule_ref": "文体附加分：参加学校、学院组织的文化艺术活动按活动证明人工核验。",
            "registration_url": "",
            "article_url": "",
            "group_qr_url": f"{demo_base}/lingnan-poetry-cover.jpg",
            "description": "参考活动素材整理：三月三诗歌节之岭南文韵知识竞赛决赛观众招募，参与现场互动与文化知识学习。",
            "requirements": ["活动通知", "报名或签到记录", "活动参与证明", "个人身份匹配证明"],
            "attachments": [],
            "images": [f"{demo_base}/lingnan-poetry-cover.jpg"],
            "tags": ["文化艺术", "文体", "观众招募"],
            "roi_score": 3.8,
        },
        {
            "source_type": "notice",
            "title": "主持人请就位决赛观众报名",
            "category": "文艺活动",
            "dimension": "arts_sports",
            "organizer": "白云校区学生组织",
            "location": "图书馆 113 报告厅",
            "start_time": "2026-06-18 19:00",
            "deadline": "2026-06-16 17:00",
            "credit_hint": "文艺活动参与记录需保留报名记录、签到和活动证明；能否加分以学院审核为准。",
            "rule_ref": "文体附加分：文艺活动参与或获奖按学校/学院认定材料核验。",
            "registration_url": "",
            "group_qr_url": f"{demo_base}/host-final-cover.jpg",
            "description": "参考活动海报整理：主持人比赛决赛观众报名，活动对象为白云校区本科学生。",
            "requirements": ["活动通知", "报名记录", "现场签到", "活动参与证明"],
            "attachments": [],
            "images": [f"{demo_base}/host-final-cover.jpg"],
            "tags": ["主持", "文体", "决赛"],
            "roi_score": 3.7,
        },
        {
            "source_type": "notice",
            "title": "广州校区反诈小课堂咨询群",
            "category": "安全教育",
            "dimension": "moral",
            "organizer": "安全教育工作组",
            "location": "线上咨询群",
            "start_time": "2026-06-05 起",
            "deadline": "2026-06-30 23:59",
            "credit_hint": "安全教育类活动通常需活动通知、签到或学习证明，具体加分以学院通知为准。",
            "rule_ref": "德育附加分：思想教育、安全教育、公益活动等需结合活动证明人工核验。",
            "registration_url": "",
            "group_qr_url": f"{demo_base}/anti-fraud-qr.jpg",
            "description": "参考活动素材整理：面向广州校区同学提供反诈宣传、咨询答疑和案例学习。演示版延长报名时间。",
            "requirements": ["活动通知", "入群或报名记录", "学习/签到证明", "个人身份匹配证明"],
            "attachments": [],
            "images": [f"{demo_base}/anti-fraud-qr.jpg"],
            "tags": ["安全教育", "德育", "线上"],
            "roi_score": 3.6,
        },
    ]

    existing_notices = db.scalars(
        select(Opportunity).where(Opportunity.source_type == "notice").order_by(Opportunity.id.asc())
    ).all()
    desired_titles = {notice["title"] for notice in notices}
    existing_by_title = {item.title: item for item in existing_notices}
    reusable_slots = [item for item in existing_notices if item.title not in desired_titles]

    for data in notices:
        item = existing_by_title.get(data["title"])
        if item is None and reusable_slots:
            item = reusable_slots.pop(0)
        if item is None:
            db.add(Opportunity(**data))
            continue
        for key, value in data.items():
            setattr(item, key, value)
    db.commit()


def seed_score_ledgers(db: Session) -> None:
    ledgers = [
        {
            "user_id": 1,
            "dimension": "moral",
            "title": "志愿服务 8 小时",
            "score": 2,
            "rule_ref": "德育志愿活动4小时1分",
            "duplicate_key": "志愿服务-2026-05",
        },
        {
            "user_id": 1,
            "dimension": "moral",
            "title": "军训副排长",
            "score": 2,
            "rule_ref": "德育军训荣誉校级",
            "duplicate_key": "军训副排长-2026",
        },
        {
            "user_id": 1,
            "dimension": "moral",
            "title": "院级文明宿舍标兵",
            "score": 3,
            "rule_ref": "德育文明宿舍院级标兵",
            "duplicate_key": "文明宿舍标兵-2026",
        },
        {
            "user_id": 1,
            "dimension": "academic",
            "title": "校级学科竞赛三等奖",
            "score": 3,
            "rule_ref": "学业其他竞赛校级三等奖",
            "duplicate_key": "校级学科竞赛",
        },
        {
            "user_id": 1,
            "dimension": "academic",
            "title": "蓝桥杯省级三等奖",
            "score": 6,
            "rule_ref": "学业其他竞赛省级三等奖",
            "duplicate_key": "蓝桥杯省级三等奖",
        },
        {
            "user_id": 1,
            "dimension": "academic",
            "title": "华为 HCIA-AI 证书",
            "score": 4,
            "rule_ref": "学业专业技术等级证书",
            "duplicate_key": "华为-HCIA-AI",
        },
        {
            "user_id": 1,
            "dimension": "arts_sports",
            "title": "主持人请就位决赛观众",
            "score": 1,
            "rule_ref": "文体活动校级参与",
            "duplicate_key": "主持人请就位-2026",
        },
        {
            "user_id": 1,
            "dimension": "arts_sports",
            "title": "诗歌节知识竞赛观众",
            "score": 1,
            "rule_ref": "文体文化活动校级参与",
            "duplicate_key": "诗歌节观众-2026",
        },
    ]
    desired_keys = {item["duplicate_key"] for item in ledgers}
    for item in db.scalars(select(ScoreLedger).where(ScoreLedger.user_id == 1)).all():
        if item.duplicate_key not in desired_keys:
            db.delete(item)
    db.flush()

    existing_by_key = {
        item.duplicate_key: item
        for item in db.scalars(select(ScoreLedger).where(ScoreLedger.user_id == 1)).all()
        if item.duplicate_key
    }
    for data in ledgers:
        item = existing_by_key.get(data["duplicate_key"])
        if item is None:
            db.add(ScoreLedger(**data))
        else:
            for key, value in data.items():
                setattr(item, key, value)
    db.commit()


def seed_honor_showcase(db: Session) -> None:
    showcase = [
        {"title": "全国高校创新英语挑战赛一等奖", "category": "证书", "image_url": "/uploads/honor-demo/english-challenge.png", "sort_order": 1},
        {"title": "Bebras 信息思维挑战优秀", "category": "证书", "image_url": "/uploads/honor-demo/bebras-2023.jpg", "sort_order": 2},
        {"title": "华为 HCIA-AI 认证", "category": "证书", "image_url": "/uploads/honor-demo/huawei-hcia-ai.png", "sort_order": 3},
        {"title": "中葡创业挑战赛 Top 50", "category": "竞赛", "image_url": "/uploads/honor-demo/macau-929.png", "sort_order": 4},
        {"title": "挑战杯院赛项目展示", "category": "竞赛", "image_url": "/uploads/honor-demo/challenge-cup-photo.jpg", "sort_order": 5},
    ]
    legacy_titles = {"蓝桥杯备赛记录", "志愿服务纪念", "专业证书展示"}
    existing = db.scalars(
        select(HonorWallItem).where(HonorWallItem.user_id == 1).order_by(HonorWallItem.sort_order, HonorWallItem.id)
    ).all()
    legacy_items = [item for item in existing if item.title in legacy_titles and not item.image_url]
    existing_by_title = {item.title: item for item in existing}

    for index, data in enumerate(showcase):
        item = existing_by_title.get(data["title"])
        if item is None and index < len(legacy_items):
            item = legacy_items[index]
        if item is None:
            db.add(HonorWallItem(user_id=1, visibility="private", **data))
        else:
            item.title = data["title"]
            item.category = data["category"]
            item.image_url = data["image_url"]
            item.sort_order = data["sort_order"]
            item.visibility = "private"
    db.commit()


def seed_audit_showcase(db: Session) -> None:
    def opportunity_id(keyword: str) -> int | None:
        return db.scalar(select(Opportunity.id).where(Opportunity.title.contains(keyword)).limit(1))

    showcase = [
        {
            "user_id": 1,
            "opportunity_id": opportunity_id("蓝桥杯"),
            "title": "蓝桥杯省级三等奖认证",
            "dimension": "academic",
            "award_level": "省级三等奖",
            "material_manifest": {
                "活动或比赛通知": True,
                "参赛或参与证明": True,
                "结果证明": True,
                "官方来源证明": True,
                "个人身份匹配证明": True,
            },
            "ai_review": {
                "recognized_text": "通知、报名记录、获奖证明和学生身份均能互相匹配。",
                "missing_materials": [],
                "rule_ref": "其他各类竞赛省级三等奖可参考 6 分，最终由管理员按细则核定。",
                "recommendation": "AI 建议通过，等待人工确认。",
            },
            "ai_confidence": 0.91,
            "risk_tags": ["AI高置信", "待人工确认"],
            "suggested_score": 6,
            "status": "pending_human",
            "admin_comment": "",
        },
        {
            "user_id": 1,
            "opportunity_id": None,
            "title": "匿名竞赛三等奖认证",
            "dimension": "academic",
            "award_level": "省级三等奖",
            "material_manifest": {"结果证明": True},
            "ai_review": {
                "recognized_text": "仅检测到结果证明，无法确认赛事来源和个人身份。",
                "missing_materials": ["活动或比赛通知", "参赛或参与证明", "官方来源证明", "个人身份匹配证明"],
                "rule_ref": "学业类竞赛加分需完整材料链，缺少来源时不得直接入账。",
                "recommendation": "材料严重不足，建议驳回或要求补齐。",
            },
            "ai_confidence": 0.62,
            "risk_tags": ["材料链不完整", "建议复核"],
            "suggested_score": 0,
            "status": "needs_more",
            "admin_comment": "请补充来源通知与个人身份匹配证明。",
        },
        {
            "user_id": 2,
            "opportunity_id": opportunity_id("全国大学生电子设计竞赛"),
            "title": "全国大学生电子设计竞赛省级二等奖认证",
            "dimension": "academic",
            "award_level": "省级二等奖",
            "material_manifest": {
                "活动或比赛通知": True,
                "参赛或参与证明": True,
                "结果证明": True,
                "官方来源证明": True,
                "个人身份匹配证明": True,
            },
            "ai_review": {
                "recognized_text": "通知、名单、获奖结果和学生身份均能互相匹配。",
                "missing_materials": [],
                "rule_ref": "重点科技竞赛省级奖项，按学业附加分条款人工核定。",
                "recommendation": "AI 建议通过，仍需管理员二次确认。",
            },
            "ai_confidence": 0.93,
            "risk_tags": ["AI高置信", "需人工确认分值"],
            "suggested_score": 18,
            "status": "pending_human",
            "admin_comment": "",
        },
        {
            "user_id": 1,
            "opportunity_id": opportunity_id("志愿服务"),
            "title": "学院志愿服务 8 小时认证",
            "dimension": "moral",
            "award_level": "8 小时",
            "material_manifest": {"活动或比赛通知": True, "参赛或参与证明": True, "结果证明": True, "个人身份匹配证明": True},
            "ai_review": {
                "recognized_text": "签到签退记录显示累计 8 小时，组织方证明与学生姓名匹配。",
                "missing_materials": [],
                "rule_ref": "德育志愿活动按 4 小时 1 分，8 小时建议 2 分。",
                "recommendation": "AI 建议通过。",
            },
            "ai_confidence": 0.98,
            "risk_tags": ["AI高置信"],
            "suggested_score": 2,
            "status": "pending_human",
            "admin_comment": "",
        },
        {
            "user_id": 2,
            "opportunity_id": opportunity_id("华为 ICT"),
            "title": "华为 ICT 大赛校赛参与证明认证",
            "dimension": "academic",
            "award_level": "校赛参与",
            "material_manifest": {"参赛或参与证明": True, "个人身份匹配证明": True},
            "ai_review": {
                "recognized_text": "存在参与截图，但缺少学院或学校通知来源与官方结果。",
                "missing_materials": ["活动或比赛通知", "官方来源证明", "结果证明"],
                "rule_ref": "竞赛参与或证书类加分需以学院通知、官方结果和细则条款共同核验。",
                "recommendation": "建议要求补材料。",
            },
            "ai_confidence": 0.52,
            "risk_tags": ["来源缺失", "结果证明不足"],
            "suggested_score": 1,
            "status": "needs_more",
            "admin_comment": "请补充官方通知或结果页截图。",
        },
        {
            "user_id": 2,
            "opportunity_id": opportunity_id("数学建模"),
            "title": "全国大学生数学建模竞赛省级一等奖认证",
            "dimension": "academic",
            "award_level": "省级一等奖",
            "material_manifest": {
                "活动或比赛通知": True,
                "参赛或参与证明": True,
                "结果证明": True,
                "官方来源证明": True,
                "个人身份匹配证明": True,
            },
            "ai_review": {
                "recognized_text": "通知、报名名单、获奖名单和学生身份均可匹配。",
                "missing_materials": [],
                "rule_ref": "学业竞赛省级一等奖，按细则人工核定分值。",
                "recommendation": "AI 建议通过，等待人工确认。",
            },
            "ai_confidence": 0.95,
            "risk_tags": ["AI高置信"],
            "suggested_score": 10,
            "status": "pending_human",
            "admin_comment": "",
        },
        {
            "user_id": 1,
            "opportunity_id": opportunity_id("挑战杯"),
            "title": "挑战杯院赛项目立项认证",
            "dimension": "academic",
            "award_level": "院赛立项",
            "material_manifest": {"活动或比赛通知": True, "参赛或参与证明": True, "个人身份匹配证明": True},
            "ai_review": {
                "recognized_text": "有立项截图和成员名单，但缺少结果公示或学院盖章材料。",
                "missing_materials": ["结果证明", "官方来源证明"],
                "rule_ref": "创新创业类项目需核验立项/结项层级和成员排序。",
                "recommendation": "建议人工复核。",
            },
            "ai_confidence": 0.71,
            "risk_tags": ["结果待确认", "成员排序需复核"],
            "suggested_score": 2,
            "status": "needs_more",
            "admin_comment": "请补充学院公示或结项证明。",
        },
        {
            "user_id": 1,
            "opportunity_id": opportunity_id("物联网"),
            "title": "全国大学生物联网设计竞赛校级二等奖认证",
            "dimension": "academic",
            "award_level": "校级二等奖",
            "material_manifest": {
                "活动或比赛通知": True,
                "参赛或参与证明": True,
                "结果证明": True,
                "官方来源证明": True,
                "个人身份匹配证明": True,
            },
            "ai_review": {
                "recognized_text": "校内通知、报名名单、获奖公示与学生身份均可匹配。",
                "missing_materials": [],
                "rule_ref": "电子信息相关科技竞赛校级奖项，按学业附加分条款人工核定。",
                "recommendation": "AI 建议通过，等待人工确认。",
            },
            "ai_confidence": 0.9,
            "risk_tags": ["AI高置信"],
            "suggested_score": 5,
            "status": "pending_human",
            "admin_comment": "",
        },
        {
            "user_id": 2,
            "opportunity_id": opportunity_id("信息安全"),
            "title": "全国大学生信息安全竞赛校级一等奖认证",
            "dimension": "academic",
            "award_level": "校级一等奖",
            "material_manifest": {
                "活动或比赛通知": True,
                "参赛或参与证明": True,
                "结果证明": True,
                "官方来源证明": True,
                "个人身份匹配证明": True,
            },
            "ai_review": {
                "recognized_text": "赛事官网、学院转发通知、参赛名单和获奖结果均能互相印证。",
                "missing_materials": [],
                "rule_ref": "信息安全竞赛按专业学科竞赛核验，分值需人工确认。",
                "recommendation": "AI 建议通过，等待人工确认。",
            },
            "ai_confidence": 0.88,
            "risk_tags": ["AI高置信"],
            "suggested_score": 5,
            "status": "pending_human",
            "admin_comment": "",
        },
        {
            "user_id": 1,
            "opportunity_id": opportunity_id("华为 ICT"),
            "title": "华为 HCIA-AI 证书认证",
            "dimension": "academic",
            "award_level": "专业证书",
            "material_manifest": {
                "活动或比赛通知": True,
                "参赛或参与证明": True,
                "结果证明": True,
                "官方来源证明": True,
                "个人身份匹配证明": True,
            },
            "ai_review": {
                "recognized_text": "证书编号、认证平台截图和个人身份信息均能对应同一学生。",
                "missing_materials": [],
                "rule_ref": "专业技术等级证书按学业附加分条款人工核定，需确认证书类型和有效期。",
                "recommendation": "AI 建议通过，等待人工确认。",
            },
            "ai_confidence": 0.92,
            "risk_tags": ["AI高置信", "需确认证书等级"],
            "suggested_score": 4,
            "status": "pending_human",
            "admin_comment": "",
        },
    ]

    desired_titles = {data["title"] for data in showcase}
    existing_by_title: dict[str, CertificationApplication] = {}
    duplicates: list[CertificationApplication] = []
    for item in db.scalars(
        select(CertificationApplication)
        .where(CertificationApplication.title.in_(desired_titles))
        .order_by(CertificationApplication.id.asc())
    ):
        if item.title in existing_by_title:
            duplicates.append(item)
        else:
            existing_by_title[item.title] = item
    for item in duplicates:
        db.delete(item)
    db.flush()

    for data in showcase:
        item = existing_by_title.get(data["title"])
        if item is None:
            db.add(CertificationApplication(**data))
        else:
            for key, value in data.items():
                setattr(item, key, value)
    db.commit()
