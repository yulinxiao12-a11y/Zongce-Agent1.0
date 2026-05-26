"""
自定义 LLM 客户端 — 支持 OpenAI 兼容 API + 工具调用
"""
import json, re, requests
import config


def _openai_client():
    """尝试使用 openai 包"""
    try:
        from openai import OpenAI
        return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    except ImportError:
        return None


def _chat_openai_sdk(messages, tools=None, temperature=0.1):
    """通过 openai SDK 调用"""
    client = _openai_client()
    if not client:
        return None
    kwargs = dict(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=config.LLM_MAX_TOKENS,
    )
    if tools:
        kwargs['tools'] = tools
    resp = client.chat.completions.create(**kwargs)
    return resp


def _chat_requests(messages, tools=None, temperature=0.1):
    """通过 requests 直接调用 OpenAI 兼容 API"""
    headers = {
        'Authorization': f'Bearer {config.LLM_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': config.LLM_MODEL,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': config.LLM_MAX_TOKENS,
    }
    if tools:
        payload['tools'] = tools

    resp = requests.post(
        f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers=headers, json=payload, timeout=60
    )
    if resp.status_code != 200:
        raise Exception(f"LLM API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


class ChatResponse:
    """统一封装响应"""
    def __init__(self, raw):
        self._raw = raw

    @property
    def content(self):
        """获取文本内容"""
        if isinstance(self._raw, dict):
            choices = self._raw.get('choices', [])
            if choices:
                msg = choices[0].get('message', {})
                return msg.get('content', '') or ''
        elif hasattr(self._raw, 'choices'):
            msg = self._raw.choices[0].message
            return msg.content or ''
        return ''

    @property
    def tool_calls(self):
        """获取工具调用"""
        if isinstance(self._raw, dict):
            choices = self._raw.get('choices', [])
            if choices:
                msg = choices[0].get('message', {})
                return msg.get('tool_calls', []) or []
        elif hasattr(self._raw, 'choices'):
            msg = self._raw.choices[0].message
            return msg.tool_calls or []
        return []


def chat(messages, tools=None, temperature=0.1):
    """统一调用入口"""
    raw = _chat_openai_sdk(messages, tools, temperature)
    if raw is None:
        raw = _chat_requests(messages, tools, temperature)
    return ChatResponse(raw)


# ══════════════════════════════════════════
# 工具定义
# ══════════════════════════════════════════

MATCH_TOOL = {
    'type': 'function',
    'function': {
        'name': 'match_comprehensive_item',
        'description': (
            '匹配一个综测加分项目。'
            '仔细阅读材料文字内容，理解其含义（活动类型、级别、角色等），'
            '然后从提供的综测项目目录中找出最匹配的项目。'
            '【关键规则】绝对不能把不同级别/类型的项目混淆，'
            '例如材料写"二级"就只能匹配"二级"项目，不能匹配"三级"或"一级"。'
            '【动态匹配数量】'
            '- 如果目录中存在与材料精确对应的项目（名称+级别完全吻合），只提交这1个，最多2个'
            '- 如果材料中的活动/证书/荣誉在目录中没有完全对应项（如"华为HCIA比赛"），'
            '  则应广泛匹配所有可能相关的项目（4-8个），降低置信度，供人工选择'
            'confidence 打分标准：'
            '- 90-100：精确命中，材料名称+级别与目录项目完全吻合'
            '- 70-89：高度相关，核心要素匹配但细节略有差异'
            '- 50-69：类别相关，材料内容方向一致但需人工确认'
            '- 30-49：间接关联，可能性较低但不排除，供参考'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'item_id': {
                    'type': 'string',
                    'description': '综测项目ID（如 M001、A049 等），必须从目录中选取',
                },
                'confidence': {
                    'type': 'integer',
                    'description': '匹配置信度 0-100，不确定时宁可偏低也不要虚高',
                    'minimum': 0,
                    'maximum': 100,
                },
                'reason': {
                    'type': 'string',
                    'description': '简短匹配理由（中文，30字以内），必须提及材料中的具体证据',
                },
            },
            'required': ['item_id', 'confidence', 'reason'],
        },
    },
}


def parse_tool_matches(response, catalog_by_id: dict) -> list:
    """从工具调用响应中提取匹配结果"""
    matches = []
    seen = set()
    for tc in response.tool_calls:
        try:
            func = tc.get('function', tc) if isinstance(tc, dict) else tc
            name = func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', '')
            if name != 'match_comprehensive_item':
                continue
            args_str = func.get('arguments', '{}') if isinstance(func, dict) else getattr(func, 'arguments', '{}')
            if isinstance(args_str, str):
                args = json.loads(args_str)
            else:
                args = args_str

            item_id = args.get('item_id', '')
            if item_id in seen or item_id not in catalog_by_id:
                continue
            seen.add(item_id)

            item = catalog_by_id[item_id]
            conf = int(args.get('confidence', 50))
            matches.append({
                'id': item_id,
                'title': item['title'],
                'description': item.get('description', ''),
                'category': item['category'],
                'category_name': item.get('category_name', ''),
                'level': item.get('level', ''),
                'score_val': item.get('score', 0),
                'icon': item.get('icon', 'fa-star'),
                'section': item.get('section', ''),
                'note': item.get('note', ''),
                'confidence': min(98, max(5, conf)),
                'decision': 'high' if conf >= 80 else ('medium' if conf >= 40 else 'low'),
                'reason': args.get('reason', 'AI综合分析匹配'),
                'raw_score': conf,
            })
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return matches


def parse_json_matches(content: str, catalog_by_id: dict) -> list:
    """从 JSON 文本响应中解析匹配结果（降级方案）"""
    jm = re.search(r'\[[\s\S]*\]', content)
    if not jm:
        return []
    try:
        raw_matches = json.loads(jm.group(0))
    except json.JSONDecodeError:
        return []

    matches = []
    seen = set()
    for m in raw_matches:
        item_id = m.get('id', '')
        if item_id in seen or item_id not in catalog_by_id:
            continue
        seen.add(item_id)
        item = catalog_by_id[item_id]
        conf = int(m.get('confidence', 50))
        matches.append({
            'id': item_id,
            'title': item['title'],
            'description': item.get('description', ''),
            'category': item['category'],
            'category_name': item.get('category_name', ''),
            'level': item.get('level', ''),
            'score_val': item.get('score', 0),
            'icon': item.get('icon', 'fa-star'),
            'section': item.get('section', ''),
            'note': item.get('note', ''),
            'confidence': min(98, max(5, conf)),
            'decision': 'high' if conf >= 80 else ('medium' if conf >= 40 else 'low'),
            'reason': m.get('reason', 'AI综合分析匹配'),
            'raw_score': conf,
        })
    return matches
