# -*- coding: utf-8 -*-
import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_FILE = BASE_DIR / 'instance' / 'honor_wall.json'
UPLOAD_DEMO_DIR = BASE_DIR / 'uploads' / 'honor-demo'
REFERENCE_DIR = ROOT_DIR / '材料' / '相关假数据参考'

DEMO_FILES = [
    {
        'source': '2025年第七届全国高校创新英语挑战赛英语翻译赛非英语专业组一等奖.png',
        'target': 'english-challenge.png',
        'title': '全国高校创新英语挑战赛一等奖',
        'category': '证书',
    },
    {
        'source': '2023Bebras.jpg',
        'target': 'bebras-2023.jpg',
        'title': 'Bebras 信息思维挑战优秀',
        'category': '证书',
    },
    {
        'source': '华为HCIA-AI.png',
        'target': 'huawei-hcia-ai.png',
        'title': '华为 HCIA-AI 认证',
        'category': '证书',
    },
    {
        'source': '929中葡创业挑战赛.png',
        'target': 'macau-929.png',
        'title': '中葡创业挑战赛 Top 50',
        'category': '竞赛',
    },
    {
        'source': '2025.10小挑院赛.jpg',
        'target': 'challenge-cup-photo.jpg',
        'title': '挑战杯院赛项目展示',
        'category': '竞赛',
    },
]


def ensure_honor_demo_uploads():
    UPLOAD_DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for item in DEMO_FILES:
        source = REFERENCE_DIR / item['source']
        target = UPLOAD_DEMO_DIR / item['target']
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def _read_all():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def _write_all(items):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')


def _next_id(items):
    return max([int(item.get('id', 0) or 0) for item in items] + [0]) + 1


def _owner_id(user_id):
    return str(user_id)


def _seed_for_owner(items, owner_id):
    ensure_honor_demo_uploads()
    next_id = _next_id(items)
    seeded = []
    for index, demo in enumerate(DEMO_FILES, start=1):
        seeded.append({
            'id': next_id,
            'user_id': owner_id,
            'title': demo['title'],
            'category': demo['category'],
            'image_url': f"/uploads/honor-demo/{demo['target']}",
            'sort_order': index,
            'visibility': 'private',
        })
        next_id += 1
    items.extend(seeded)
    _write_all(items)
    return seeded


def load_honors(user_id):
    owner_id = _owner_id(user_id)
    items = _read_all()
    owned = [item for item in items if str(item.get('user_id')) == owner_id]
    if not owned:
        owned = _seed_for_owner(items, owner_id)
    return sorted(owned, key=lambda item: (int(item.get('sort_order') or 0), int(item.get('id') or 0)))


def add_honor(user_id, data):
    owner_id = _owner_id(user_id)
    items = _read_all()
    owned = [item for item in items if str(item.get('user_id')) == owner_id]
    item = {
        'id': _next_id(items),
        'user_id': owner_id,
        'title': (data.get('title') or '').strip(),
        'category': data.get('category') or '证书',
        'image_url': data.get('image_url') or '',
        'sort_order': data.get('sort_order') or len(owned) + 1,
        'visibility': data.get('visibility') or 'private',
    }
    items.append(item)
    _write_all(items)
    return item


def update_honor(user_id, honor_id, data):
    owner_id = _owner_id(user_id)
    items = _read_all()
    for item in items:
        if int(item.get('id') or 0) == int(honor_id) and str(item.get('user_id')) == owner_id:
            for key in ['title', 'category', 'image_url', 'sort_order', 'visibility']:
                if key in data:
                    item[key] = data[key]
            _write_all(items)
            return item
    return None


def delete_honor(user_id, honor_id):
    owner_id = _owner_id(user_id)
    items = _read_all()
    next_items = [
        item for item in items
        if not (int(item.get('id') or 0) == int(honor_id) and str(item.get('user_id')) == owner_id)
    ]
    if len(next_items) == len(items):
        return False
    _write_all(next_items)
    return True
