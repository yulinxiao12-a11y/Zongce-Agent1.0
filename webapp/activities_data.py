# -*- coding: utf-8 -*-
# 近期活动数据 - 管理员可发布，AI辅助识别填充
import json, os

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'activities.json')

# 默认种子数据
DEFAULT_ACTIVITIES = [
    {"id":"ACT1","title":"电子与信息学院2025年学风建设月系列活动","category":"院级活动","level":"院级","date":"2025-05-01","organizer":"电子与信息学院学生会","description":"包括学习经验分享会、优秀笔记展评、学习小组组建等活动","status":"进行中","related_score":"品德+1-3分"},
    {"id":"ACT2","title":"挑战杯全国大学生课外学术科技作品竞赛校赛","category":"学科竞赛","level":"校级","date":"2025-06-15","organizer":"校团委、教务处","description":"挑战杯校赛选拔，优秀作品推荐参加省赛","status":"报名中","related_score":"学业+10-40分"},
    {"id":"ACT3","title":"第六届广东省大学生电子设计竞赛","category":"学科竞赛","level":"省级","date":"2025-08-20","organizer":"广东省教育厅","description":"省级电子设计竞赛，面向全省高校电子信息类专业学生","status":"即将开始","related_score":"学业+12-40分"},
    {"id":"ACT4","title":"电信学院2025年暑期三下乡社会实践活动","category":"社会实践","level":"院级","date":"2025-07-10","organizer":"电子与信息学院团委","description":"组织学生赴乡村开展科技支教、家电维修等志愿服务","status":"报名中","related_score":"品德+4-8分"},
    {"id":"ACT5","title":"全国大学生数学建模竞赛（2025）","category":"学科竞赛","level":"国家级","date":"2025-09-11","organizer":"中国工业与应用数学学会","description":"全国大学生数学建模竞赛，三人组队参赛","status":"即将开始","related_score":"学业+15-40分"},
]

def load_activities():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # Save defaults
    save_activities(DEFAULT_ACTIVITIES)
    return DEFAULT_ACTIVITIES[:]

def save_activities(activities):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(activities, f, ensure_ascii=False, indent=2)

ACTIVITY_FIELDS = [
    'title', 'category', 'level', 'date', 'start_time', 'deadline',
    'organizer', 'description', 'status', 'related_score', 'location',
    'official_url', 'registration_url', 'contact_email', 'article_url',
    'group_qr_url', 'images', 'attachments', 'season_months',
    'credit_hint', 'rule_ref', 'requirements', 'tags',
]


def add_activity(data):
    activities = load_activities()
    new_id = 'ACT' + str(len(activities) + 1)
    activity = {
        'id': new_id,
        'title': data.get('title', ''),
        'category': data.get('category', '院级活动'),
        'level': data.get('level', '院级'),
        'date': data.get('date', ''),
        'start_time': data.get('start_time', ''),
        'deadline': data.get('deadline', ''),
        'organizer': data.get('organizer', ''),
        'description': data.get('description', ''),
        'status': data.get('status', '即将开始'),
        'related_score': data.get('related_score', ''),
        'location': data.get('location', ''),
        'official_url': data.get('official_url', ''),
        'registration_url': data.get('registration_url', ''),
        'contact_email': data.get('contact_email', ''),
        'article_url': data.get('article_url', ''),
        'group_qr_url': data.get('group_qr_url', ''),
        'images': data.get('images', []),
        'attachments': data.get('attachments', []),
        'season_months': data.get('season_months', ''),
        'credit_hint': data.get('credit_hint', ''),
        'rule_ref': data.get('rule_ref', ''),
        'requirements': data.get('requirements', []),
        'tags': data.get('tags', []),
    }
    activities.append(activity)
    save_activities(activities)
    return activity


def update_activity(act_id, data):
    activities = load_activities()
    for a in activities:
        if a['id'] == act_id:
            for key in ACTIVITY_FIELDS:
                if key in data:
                    a[key] = data[key]
            save_activities(activities)
            return a
    return None

def delete_activity(act_id):
    activities = load_activities()
    activities = [a for a in activities if a['id'] != act_id]
    save_activities(activities)
    return True
