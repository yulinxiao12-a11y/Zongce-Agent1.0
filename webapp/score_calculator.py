# -*- coding: utf-8 -*-
"""
确定性规则计算引擎 — 身份系数折算 + 多职务规则 + 等比归一化
依据《2025年7月电信学院综测细则（公示版）》设计

核心原则: 一旦匹配到细则条款，使用确定性 Python 代数算子而非 LLM 算分，
从根源上杜绝"计算幻觉"。
"""
import re
from typing import Optional


# ══════════════════════════════════════════
# 1. 角色/排名系数 ─ 细则规定
# ══════════════════════════════════════════
# 细则原文: "前3名按100%加分；4-5名按70%加分；其余成员按25%加分"
# 适用于: 重点科技竞赛（互联网+/大挑/小挑/电子设计竞赛）的团队项目

RANK_DETECT_PATTERNS = [
    # 高优先级: 明确排名数字（多种表达）
    (r'(?:排名|名次)[^\d]{0,4}第?\s*(\d+)\s*(?:[名位]|$|\s)', 'numbered'),  # "排名第4" / "排名第4名" / "名次: 4"
    (r'第\s*(\d+)\s*(?:名|位)(?!\s*(?:奖|等奖))', 'numbered'),           # "第4名" (排除"第1名"=一等奖的情况)
    (r'\(排名\s*(\d+)\s*\)', 'numbered'),                                 # "(排名4)"
    (r'(?:排名|名次)\s*[:：]\s*(\d+)', 'numbered'),                       # "排名: 4"
    (r'(\d+)\s*(?:st|nd|rd|th)\s*(?:place|position)', 'numbered'),       # "4th place"
    # 角色描述（优先级低于数字排名）
    (r'(?:负责|队长|组长|主持|牵头|负责人|第一作者|通讯作者)', 'leader'),
    (r'(?:核心成员|骨干|副队长|副组长|第二作者|第三作者)', 'core'),
    (r'(?:普通成员|一般成员|队员|组员|参与|成员|第四作者|第五作者)', 'member'),
]

# 数字排名 → 系数映射
def _number_to_rank_coefficient(rank_num: int) -> tuple[str, float]:
    """将数字排名映射到角色和系数"""
    if rank_num <= 3:
        return 'leader', 1.0
    elif rank_num <= 5:
        return 'core', 0.7
    else:
        return 'member', 0.25


RANK_COEFFICIENTS = {
    'leader':  1.0,   # 负责人/前3名 → 100%
    'core':    0.7,   # 核心成员/4-5名 → 70%
    'member':  0.25,  # 普通成员/其余 → 25%
    'solo':    1.0,   # 个人参赛 → 100% (默认)
}

RANK_LABELS = {
    'leader': '负责人/前3名(100%)',
    'core': '核心成员/4-5名(70%)',
    'member': '普通成员(25%)',
    'solo': '个人参赛(100%)',
}

# 需要应用排名系数的赛事关键词（团队赛）
TEAM_COMPETITION_KEYWORDS = [
    '互联网+', '挑战杯', '大挑', '小挑', '创青春', '电子设计竞赛',
    '智能车', '智能汽车', '机器人大赛', '计算机设计大赛',
    '数学建模', '电子设计', '集成电路', '嵌入式', '物联网',
    '软件杯', '服创大赛', '三创赛', '节能减排', '机械创新',
    '工程训练', '光电设计', '化学实验', '生物医学',
    '蓝桥杯',  # 虽然主要是个人赛，也有团队赛
]

# 个人赛关键词（不应用排名系数）
SOLO_COMPETITION_KEYWORDS = [
    '英语竞赛', '英语大赛', '英语翻译', '英语写作', '英语阅读',
    '数学竞赛', '物理竞赛', '化学竞赛',
    '个人赛', '个人项目', '单项赛',
]


def detect_rank_from_text(text: str, item_title: str = '') -> dict:
    """从材料文本和匹配项目名称中检测学生角色/排名

    返回: {
        'rank_type': str,       # 'numbered' | 'leader' | 'core' | 'member' | 'solo'
        'rank_label': str,      # 中文描述
        'coefficient': float,   # 系数值 0.25~1.0
        'rank_number': int|None,# 具体排名数字
        'is_team_event': bool,  # 是否团队赛事
    }
    """
    source = f'{item_title}\n{text}'

    # ── 先判断是否个人赛 ──
    for kw in SOLO_COMPETITION_KEYWORDS:
        if kw in source:
            return {
                'rank_type': 'solo',
                'rank_label': RANK_LABELS['solo'],
                'coefficient': RANK_COEFFICIENTS['solo'],
                'rank_number': None,
                'is_team_event': False,
            }

    # ── 检测数字排名 ──
    for pattern, rtype in RANK_DETECT_PATTERNS:
        match = re.search(pattern, source)
        if match:
            if rtype == 'numbered':
                try:
                    rank_num = int(match.group(1))
                    if rank_num >= 1 and rank_num <= 50:  # 合理范围
                        rank_type, coeff = _number_to_rank_coefficient(rank_num)
                        return {
                            'rank_type': rank_type,
                            'rank_label': RANK_LABELS[rank_type],
                            'coefficient': coeff,
                            'rank_number': rank_num,
                            'is_team_event': True,
                        }
                except (ValueError, IndexError):
                    pass
            elif rtype in RANK_COEFFICIENTS:
                return {
                    'rank_type': rtype,
                    'rank_label': RANK_LABELS[rtype],
                    'coefficient': RANK_COEFFICIENTS[rtype],
                    'rank_number': None,
                    'is_team_event': True,
                }

    # ── 检查是否为团队赛 ──
    is_team = False
    for kw in TEAM_COMPETITION_KEYWORDS:
        if kw in source:
            is_team = True
            break

    # ── 默认: 个人参赛 ──
    return {
        'rank_type': 'solo',
        'rank_label': RANK_LABELS['solo'],
        'coefficient': RANK_COEFFICIENTS['solo'],
        'rank_number': None,
        'is_team_event': is_team,
    }


def apply_rank_coefficient(base_score: float, rank_info: dict) -> tuple[float, str]:
    """应用排名系数，返回 (调整后分数, 计算说明)"""
    coeff = rank_info.get('coefficient', 1.0)
    adjusted = round(base_score * coeff, 1)
    if coeff == 1.0:
        return adjusted, f'{base_score} × 1.0 = {adjusted}'
    else:
        return adjusted, f'{base_score} × {coeff}({rank_info["rank_label"]}) = {adjusted}'


# ══════════════════════════════════════════
# 2. 多职务去重规则 ─ 细则规定
# ══════════════════════════════════════════
# 细则原文: "身兼多职者仅加最高一项职务分，其余按50%折算，
#           最高上限2分，且所有职务分之和不得超过12分"

def apply_multi_position_rule(position_scores: list[dict]) -> dict:
    """应用多职务去重规则

    输入: [{'id': 'M001', 'title': '校学生会主席', 'score': 12}, ...]
    返回: {
        'adjusted_scores': [{'id': ..., 'original': ..., 'adjusted': ..., 'rule': ...}],
        'total': float,
        'detail': str,
    }
    """
    if not position_scores:
        return {'adjusted_scores': [], 'total': 0.0, 'detail': '无职务加分'}

    if len(position_scores) == 1:
        return {
            'adjusted_scores': [{
                **position_scores[0],
                'original': position_scores[0]['score'],
                'adjusted': position_scores[0]['score'],
                'coefficient': 1.0,
                'rule': '单一职务，全额加分',
            }],
            'total': position_scores[0]['score'],
            'detail': f'单一职务"{position_scores[0].get("title","")}"全额{position_scores[0]["score"]}分',
        }

    # 按分数降序排列
    sorted_positions = sorted(position_scores, key=lambda x: x.get('score', 0), reverse=True)
    highest = sorted_positions[0]
    rest = sorted_positions[1:]

    adjusted = [{
        **highest,
        'original': highest['score'],
        'adjusted': highest['score'],
        'coefficient': 1.0,
        'rule': '最高职务，全额加分',
    }]

    total = highest['score']
    rest_total = 0.0

    for pos in rest:
        half_score = round(pos['score'] * 0.5, 1)
        # 其余职务50%折算，但每项上限2分
        capped_half = min(half_score, 2.0)
        rest_total += capped_half
        adjusted.append({
            **pos,
            'original': pos['score'],
            'adjusted': capped_half,
            'coefficient': 0.5,
            'rule': f'次要职务50%折算({pos["score"]}×0.5={half_score}，单顶上限2分→{capped_half}分)',
        })

    total += rest_total
    # 所有职务分之和不得超过12分
    final_total = min(total, 12.0)
    cap_note = f'，触发12分上限' if total > 12 else ''

    titles = '、'.join(p.get('title', '') for p in sorted_positions)
    return {
        'adjusted_scores': adjusted,
        'total': final_total,
        'detail': f'多职务"{titles}"：最高{highest["score"]}分+其余50%折算{rest_total}分={total}分{cap_note}',
    }


# ══════════════════════════════════════════
# 3. 班级等比归一化 ─ 细则规定
# ══════════════════════════════════════════
# 细则原文:
#   德育附加分: F = min(S_person / S_max × 30, S_person)  if S_max > 30
#   学业附加分: F = min(S_person / S_max × 20, S_person)  if S_max > 20
#   文体附加分: F = min(S_person / S_max × 40, S_person)  if S_max > 40

NORMALIZATION_CAPS = {
    'moral':    30,  # 德育附加分上限
    'academic': 20,  # 学业附加分上限
    'sports':   40,  # 文体附加分上限
}

NORMALIZATION_LABELS = {
    'moral':    '德育',
    'academic': '学业',
    'sports':   '文体',
}


def normalize_class_score(
    personal_score: float,
    class_max_score: float,
    dimension: str,
) -> tuple[float, str]:
    """班级等比归一化

    Args:
        personal_score: 学生原始附加分
        class_max_score: 班级最高原始附加分 (S_max)
        dimension: 'moral' | 'academic' | 'sports'

    Returns:
        (归一化后分数, 计算过程说明)
    """
    cap = NORMALIZATION_CAPS.get(dimension, 30)
    label = NORMALIZATION_LABELS.get(dimension, dimension)

    if class_max_score <= cap or class_max_score <= 0:
        # 班级最高分未超过上限，无需归一化
        result = min(personal_score, cap)
        if result < personal_score:
            return result, f'{label}: {personal_score}分(已达个人{cap}分上限，班级最高{class_max_score}≤{cap}无需归一化)'
        return personal_score, f'{label}: {personal_score}分(班级最高{class_max_score}≤{cap}，无需归一化)'

    # 需要归一化: F = S_person / S_max × cap
    ratio = personal_score / class_max_score
    normalized = round(ratio * cap, 2)
    result = min(normalized, personal_score)  # 不超过原始分

    return result, (
        f'{label}等比归一化: {personal_score}/{class_max_score}×{cap} = {normalized:.2f}分'
        f'(班级最高{class_max_score}>{cap}触发归一化)'
    )


def normalize_all_dimensions(
    personal_scores: dict[str, float],
    class_max_scores: dict[str, float],
) -> dict:
    """对三个维度的附加分全部进行归一化

    Args:
        personal_scores: {'moral': 25, 'academic': 15, 'sports': 10}
        class_max_scores: {'moral': 42, 'academic': 28, 'sports': 35}

    Returns:
        {'moral': (18.33, '说明'), 'academic': (12.0, '说明'), 'sports': (10, '说明')}
    """
    results = {}
    for dim in ['moral', 'academic', 'sports']:
        personal = personal_scores.get(dim, 0)
        class_max = class_max_scores.get(dim, 0)
        score, detail = normalize_class_score(personal, class_max, dim)
        results[dim] = {
            'original': personal,
            'class_max': class_max,
            'normalized': score,
            'detail': detail,
        }
    return results


# ══════════════════════════════════════════
# 4. 综合算分入口 ─ 一条龙处理
# ══════════════════════════════════════════

def calculate_deterministic_score(
    match: dict,
    extracted_text: str = '',
    class_max_scores: dict = None,
) -> dict:
    """确定性算分入口：对单个匹配结果应用所有确定规则

    Args:
        match: LLM匹配结果，含 id/title/category/score_val/level
        extracted_text: OCR提取的文本
        class_max_scores: 可选，班级各维度最高原始附加分

    Returns:
        增强的match，新增字段:
            - deterministic_score: 确定性计算后的分数
            - rank_info: 角色/排名检测结果
            - score_detail: 算分过程说明
    """
    base_score = float(match.get('score_val', match.get('score', 0)))
    category = match.get('category', '')
    item_title = match.get('title', '')

    # Step 1: 检测排名/角色
    rank_info = detect_rank_from_text(extracted_text, item_title)

    # Step 2: 应用排名系数
    adjusted_score, coeff_detail = apply_rank_coefficient(base_score, rank_info)

    # Step 3: 归一化 (如果提供了班级最高分)
    norm_detail = ''
    final_score = adjusted_score
    if class_max_scores and category in ('moral', 'academic', 'sports'):
        class_max = class_max_scores.get(category, 0)
        if class_max > 0:
            final_score, norm_detail_text = normalize_class_score(
                adjusted_score, class_max, category
            )
            final_score = round(final_score, 2)
            norm_detail = f' → {norm_detail_text}'

    # 构建算分链
    steps = [f'基准分{base_score}']
    if rank_info['coefficient'] != 1.0:
        steps.append(coeff_detail)
    if norm_detail:
        steps.append(norm_detail.lstrip(' → '))
    score_chain = ' | '.join(steps)

    match['deterministic_score'] = final_score
    match['rank_info'] = rank_info
    match['score_detail'] = score_chain
    match['base_score'] = base_score
    match['coefficient_applied'] = rank_info['coefficient'] != 1.0

    return match
