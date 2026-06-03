# -*- coding: utf-8 -*-
"""
易混淆项目精细化区分引擎 — 基于区分信号的置信度惩罚/奖励
覆盖目录中全部43组易混淆项，涉及170+个综测项目

核心策略:
1. 混淆组检测: 检查匹配结果中是否存在同一混淆组的多个项目
2. 区分信号提取: 从OCR文本中提取级别、数字、正副、校院等区分特征
3. 置信度调整:
   - 有明确区分信号的项目: +奖励(提升置信度)
   - 无区分信号的同组项目: -惩罚(降低置信度)
   - 多个同组项目并列无信号: 全部施加模糊惩罚
"""
import re
from typing import Optional


# ══════════════════════════════════════════
# 1. 核心混淆组定义
# ══════════════════════════════════════════
# 格式: { 'group_id': str, 'items': [id列表], 'distinguishers': {信号名: 区分规则} }

CONFUSION_GROUPS = [
    # ────────────────────────────────────────
    # 一、等级证书 (4组)
    # ────────────────────────────────────────

    # 1a: 计算机等级 一级/二级/三级/四级
    {
        'group_id': 'ncre_level',
        'name': '计算机等级考试',
        'items': ['A047', 'A048', 'A049', 'A050'],
        'id_to_label': {'A047': '四级', 'A048': '三级', 'A049': '二级', 'A050': '一级'},
        'signals': {
            '四级': [r'(?:计算机|NCRE).{0,6}(?:四级|4级|level\s*4)',
                      r'(?:四级|4级).{0,4}(?:计算机|NCRE|合格|证书|通过)'],
            '三级': [r'(?:计算机|NCRE).{0,6}(?:三级|3级|level\s*3)',
                      r'(?:三级|3级).{0,4}(?:计算机|NCRE|合格|证书|通过)'],
            '二级': [r'(?:计算机|NCRE).{0,6}(?:二级|2级|level\s*2)',
                      r'(?:二级|2级).{0,4}(?:计算机|NCRE|合格|证书|通过|MS|WPS|Python|Java|C\+\+|Access|Office)'],
            '一级': [r'(?:计算机|NCRE).{0,6}(?:一级|1级|level\s*1)',
                      r'(?:一级|1级).{0,4}(?:计算机|NCRE|合格|证书|通过)'],
        },
        'penalty_ambiguous': 20,  # 无法区分时每个匹配项-20%
        'bonus_clear': 8,         # 有明确区分信号时+8%
    },

    # 1b: 英语等级 四级/六级
    {
        'group_id': 'cet_level',
        'name': '英语等级考试',
        'items': ['A042', 'A043'],
        'id_to_label': {'A042': '四级', 'A043': '六级'},
        'signals': {
            '四级': [r'CET[-\s]?4\b', r'英语四级', r'大学英语四级', r'四级成绩', r'四级证书',
                      r'四级425', r'四级通过', r'CET4'],
            '六级': [r'CET[-\s]?6\b', r'英语六级', r'大学英语六级', r'六级成绩', r'六级证书',
                      r'六级425', r'六级通过', r'CET6'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 10,
    },

    # 1c: 普通话等级 二甲/二乙/三甲
    {
        'group_id': 'putonghua_level',
        'name': '普通话等级',
        'items': ['A051', 'A052', 'A053'],
        'id_to_label': {'A051': '二甲及以上', 'A052': '二乙', 'A053': '三甲'},
        'signals': {
            '二甲及以上': [r'二甲', r'一[甲乙]', r'普通话.{0,4}(?:二级甲等|一级|2甲|1[甲乙])'],
            '二乙': [r'二乙', r'普通话.{0,4}(?:二级乙等|2乙)'],
            '三甲': [r'三甲', r'普通话.{0,4}(?:三级甲等|3甲|三级)'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 1d: 专业技术等级 高级/中级/初级
    {
        'group_id': 'tech_cert_level',
        'name': '专业技术等级证书',
        'items': ['A044', 'A045', 'A046'],
        'id_to_label': {'A044': '高级', 'A045': '中级', 'A046': '初级'},
        'signals': {
            '高级': [r'HCIE', r'高级', r'高级工程师', r'高级认证', r'Expert'],
            '中级': [r'HCIP', r'中级', r'中级工程师', r'中级认证', r'Professional'],
            '初级': [r'HCIA', r'初级', r'初级认证', r'Associate', r'入门'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 10,
    },

    # ────────────────────────────────────────
    # 二、职务层级 (7组)
    # ────────────────────────────────────────

    # 2a: 校学生会主席正/副 (已在校验中覆盖，这里加强)
    {
        'group_id': 'student_union_chair',
        'name': '校学生会主席团正/副',
        'items': ['M001', 'M002'],
        'id_to_label': {'M001': '正职', 'M002': '副职'},
        'signals': {
            '正职': [r'(?:校学生会|主席团).{0,3}(?:正|主席(?!团))', r'(?!副)(?:主席团正式|正职)'],
            '副职': [r'副主席', r'副职', r'主席团副', r'学生会副主席'],
        },
        'penalty_ambiguous': 15,
        'bonus_clear': 6,
    },

    # 2b-2c: 校/院学生干部层级 (主席/部长/干事)
    {
        'group_id': 'school_union_hierarchy',
        'name': '校学生会层级',
        'items': ['M001', 'M002', 'M003', 'M004', 'M005'],
        'id_to_label': {'M001': '主席正', 'M002': '主席副', 'M003': '部长正', 'M004': '部长副', 'M005': '干事'},
        'signals': {
            '主席正': [r'(?:主席团|主席)(?!.*(?:副|部长|干事))'],
            '主席副': [r'(?:副主席|主席团.*副)'],
            '部长正': [r'(?:部长|负责人)(?!.*(?:副|干事))', r'部长正职'],
            '部长副': [r'副部长'],
            '干事': [r'干事(?!.*(?:部长|主席))', r'干事满一年'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 2d: 院学生会层级
    {
        'group_id': 'college_union_hierarchy',
        'name': '院学生会层级',
        'items': ['M019', 'M020', 'M021', 'M022'],
        'id_to_label': {'M019': '主席/副书记', 'M020': '部长', 'M021': '干事', 'M022': '预干'},
        'signals': {
            '主席/副书记': [r'(?:院.{0,4}(?:主席|团总支副书记)|主席团(?!.*(?:部长|干事|预干)))'],
            '部长': [r'(?:院.{0,4}部长|部长(?!.*(?:干事|预干)))'],
            '干事': [r'(?:干事(?!.*预)|院.{0,4}干事)'],
            '预干': [r'预干'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 2e: 科技站考核 优秀/合格
    {
        'group_id': 'tech_station_grade',
        'name': '科技站考核优秀/合格',
        'items': ['M023', 'M024'],
        'id_to_label': {'M023': '优秀', 'M024': '合格'},
        'signals': {
            '优秀': [r'(?:科技站|技术部).{0,4}优秀', r'考核优秀'],
            '合格': [r'(?:科技站|技术部).{0,4}合格', r'考核合格'],
        },
        'penalty_ambiguous': 25,
        'bonus_clear': 10,
    },

    # 2f: 工作小组 组长/组员
    {
        'group_id': 'work_group_lead',
        'name': '院级工作小组组长/组员',
        'items': ['M027a', 'M027b'],
        'id_to_label': {'M027a': '组长', 'M027b': '组员'},
        'signals': {
            '组长': [r'组长', r'负责人'],
            '组员': [r'组员', r'成员(?!.*组长)'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 7,
    },

    # 2g: 党支部 副书记/委员
    {
        'group_id': 'party_branch_role',
        'name': '学生党支部副书记/委员',
        'items': ['M026a', 'M026b'],
        'id_to_label': {'M026a': '副书记', 'M026b': '委员'},
        'signals': {
            '副书记': [r'副书记', r'党支部副'],
            '委员': [r'(?:党支部|支部)委员', r'(?<!副)书记(?!.*副)'],
        },
        'penalty_ambiguous': 15,
        'bonus_clear': 6,
    },

    # ────────────────────────────────────────
    # 三、校/院级别混淆 (5组)
    # ────────────────────────────────────────

    # 3a-3c: 校vs院 荣誉称号
    {
        'group_id': 'honor_school_college',
        'name': '荣誉称号校vs院',
        'items': ['M052', 'M053', 'M054'],
        'id_to_label': {'M052': '省级', 'M053': '校级', 'M054': '院级'},
        'signals': {
            '省级': [r'省级', r'全省', r'广东省.{0,3}(?:优秀|先进|三好)'],
            '校级': [r'校级', r'全校', r'广东技术师范大学.{0,3}(?:优秀|先进|三好)'],
            '院级': [r'院级', r'电信学院|电子与信息学院.{0,3}(?:优秀|先进)'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 8,
    },

    # 3b: 校vs院 文体先进个人
    {
        'group_id': 'sports_person_school_college',
        'name': '文体先进个人校vs院',
        'items': ['M058', 'M059'],
        'id_to_label': {'M058': '校级', 'M059': '院级'},
        'signals': {
            '校级': [r'校级.{0,4}(?:文体|先进)', r'(?:校|全校).{0,4}(?:文体|先进)'],
            '院级': [r'院级.{0,4}(?:文体|先进)', r'(?:院|学院).{0,4}(?:文体|先进)'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 3c: 文明宿舍 校/院 × 标兵/普通 4项矩阵
    {
        'group_id': 'civilized_dormitory',
        'name': '文明宿舍(校/院×标兵/普通)',
        'items': ['M066', 'M067', 'M068', 'M069'],
        'id_to_label': {'M066': '校标兵', 'M067': '校普通', 'M068': '院标兵', 'M069': '院普通'},
        'signals': {
            '校标兵': [r'(?:校级|全校).{0,4}(?:文明宿舍)?标兵', r'校级文明宿舍标兵'],
            '校普通': [r'(?:校级|全校).{0,4}文明宿舍(?!标兵)', r'校级文明宿舍'],
            '院标兵': [r'(?:院级|学院).{0,4}(?:文明宿舍)?标兵', r'院级文明宿舍标兵'],
            '院普通': [r'(?:院级|学院).{0,4}文明宿舍(?!标兵)', r'院级文明宿舍'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 3d: 活动获奖校vs院
    {
        'group_id': 'activity_award_school_college',
        'name': '活动获奖校vs院',
        'items': ['M044', 'M045', 'M046', 'M047'],
        'id_to_label': {'M044': '校第一', 'M045': '校二三', 'M046': '院第一', 'M047': '院其他'},
        'signals': {
            '校第一': [r'(?:校级|全校|校外).{0,6}(?:第一|1等|冠军)'],
            '校二三': [r'(?:校级|全校|校外).{0,6}(?:第二|第三|2等|3等|亚军|季军)'],
            '院第一': [r'(?:院级|学院).{0,6}(?:第一|1等)'],
            '院其他': [r'(?:院级|学院).{0,6}(?:第二|第三|2等|3等|其他|优秀)'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 7,
    },

    # ────────────────────────────────────────
    # 四、竞赛奖级阶梯 (6组)
    # ────────────────────────────────────────

    # 4a-4b: 四大赛事 奖级 + 级别
    {
        'group_id': 'four_key_competitions_prize',
        'name': '四大赛事奖级阶梯',
        'items': [
            'A007I','A007D','A007X','A007E','A008I','A008D','A008X','A008E',
            'A009I','A009D','A009X','A009E','A010I','A010D','A010X','A010E',
            'A011I','A011D','A011X','A011E','A012I','A012D','A012X','A012E',
            'A013I','A013D','A013X','A013E','A014I','A014D','A014X','A014E',
            'A015I','A015D','A015X','A015E','A016I','A016D','A016X','A016E',
            'A017I','A017D','A017X','A017E',
        ],
        'id_to_label': {},  # 动态生成
        'signals': {
            '国最高': [r'(?:国家级|全国|国赛).{0,4}(?:最高|特等|一等|金奖|特奖)'],
            '省最高': [r'(?:省级|省赛).{0,4}(?:最高|特等|一等|金奖)'],
            '省次级': [r'(?:省级|省赛).{0,4}(?:二等|次级|银奖)'],
            '省三等': [r'(?:省级|省赛).{0,4}(?:三等|铜奖)'],
            '省参赛': [r'(?:省级|省赛).{0,4}(?:参赛|四等|优秀奖|参与)'],
            '校最高': [r'(?:校级|校赛).{0,4}(?:最高|特等|一等|金奖)'],
            '校次级': [r'(?:校级|校赛).{0,4}(?:二等|次级)'],
            '校三等': [r'(?:校级|校赛).{0,4}(?:三等|参赛)'],
            '院最高': [r'(?:院级|院赛).{0,4}(?:最高|特等|一等|金奖)'],
            '院次级': [r'(?:院级|院赛).{0,4}(?:二等|次级)'],
            '院三等': [r'(?:院级|院赛).{0,4}(?:三等|参赛)'],
        },
        'penalty_ambiguous': 25,
        'bonus_clear': 12,
        # 赛事类型子区分 (互联网+ vs 大挑 vs 小挑 vs 电赛)
        'sub_signals': {
            '互联网+': [r'互联网\+', r'互联网加', r'互联网大赛', r'中国国际'],
            '大挑': [r'(?:大挑|课外学术科技|学术科技作品|挑战杯.{0,4}(?:学术|科技|发明|调研))'],
            '小挑': [r'(?:小挑|创青春|创业计划|商业计划|创业大赛.{0,4}挑战杯)'],
            '电子设计': [r'电子设计', r'电赛', r'TI杯', r'全国大学生电子'],
        },
    },

    # 4c: 其他专业竞赛 16项
    {
        'group_id': 'other_professional_competition',
        'name': '其他专业竞赛级别奖级',
        'items': [
            'A026','A027','A028','A029','A030','A031','A032','A033',
            'A034','A035','A036','A037','A038','A039','A040','A041',
        ],
        'id_to_label': {
            'A026': '国最高', 'A027': '国二等', 'A028': '国三等', 'A029': '国其他',
            'A030': '省最高', 'A031': '省二等', 'A032': '省三等', 'A033': '省其他',
            'A034': '校最高', 'A035': '校二等', 'A036': '校三等', 'A037': '校其他',
            'A038': '院一等', 'A039': '院二等', 'A040': '院三等', 'A041': '院其他',
        },
        'signals': {
            '国最高': [r'(?:国家级|全国|国赛).{0,4}(?:一等|特等|最高|金奖)'],
            '国二等': [r'(?:国家级|全国|国赛).{0,4}(?:二等|银奖)'],
            '国三等': [r'(?:国家级|全国|国赛).{0,4}(?:三等|铜奖)'],
            '国其他': [r'(?:国家级|全国|国赛).{0,4}(?:其他|优秀|参赛)'],
            '省最高': [r'(?:省级|省赛).{0,4}(?:一等|特等|最高|金奖)(?!.*国)'],
            '省二等': [r'(?:省级|省赛).{0,4}(?:二等|银奖)(?!.*国)'],
            '省三等': [r'(?:省级|省赛).{0,4}(?:三等|铜奖)(?!.*国)'],
            '省其他': [r'(?:省级|省赛).{0,4}(?:其他|优秀|参赛)(?!.*国)'],
            '校最高': [r'(?:校级|校赛).{0,4}(?:一等|特等|最高|金奖)(?!.*(?:省|国))'],
            '校二等': [r'(?:校级|校赛).{0,4}(?:二等|银奖)(?!.*(?:省|国))'],
            '校三等': [r'(?:校级|校赛).{0,4}(?:三等|铜奖)(?!.*(?:省|国))'],
            '校其他': [r'(?:校级|校赛).{0,4}(?:其他|优秀|参赛)(?!.*(?:省|国))'],
            '院一等': [r'(?:院级|院赛).{0,4}(?:一等|特等|最高|金奖)'],
            '院二等': [r'(?:院级|院赛).{0,4}(?:二等|银奖)'],
            '院三等': [r'(?:院级|院赛).{0,4}(?:三等|铜奖)'],
            '院其他': [r'(?:院级|院赛).{0,4}(?:其他|优秀|参赛)'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 10,
    },

    # 4d: 非专业竞赛 (文体类的S037-S048)
    {
        'group_id': 'non_professional_competition',
        'name': '非专业竞赛级别奖级',
        'items': ['S037','S038','S039','S040','S041','S042','S043','S044','S045','S046','S047','S048'],
        'id_to_label': {
            'S037': '国一等', 'S038': '国二等', 'S039': '国三等', 'S040': '国其他',
            'S041': '省一等', 'S042': '省二等', 'S043': '省三等', 'S044': '省其他',
            'S045': '校一等', 'S046': '校二等', 'S047': '校三等', 'S048': '校其他',
        },
        'signals': {
            '国一等': [r'(?:国家级|全国).{0,4}(?:一等|特等|最高|金奖).{0,4}(?:演讲|辩论|征文|文艺)'],
            '国二等': [r'(?:国家级|全国).{0,4}(?:二等|银奖).{0,4}(?:演讲|辩论|征文|文艺)'],
            '国三等': [r'(?:国家级|全国).{0,4}(?:三等|铜奖).{0,4}(?:演讲|辩论|征文|文艺)'],
            '国其他': [r'(?:国家级|全国).{0,4}(?:其他|优秀|参赛).{0,4}(?:演讲|辩论|征文|文艺)'],
            '省一等': [r'(?:省级|省赛).{0,4}(?:一等|特等|最高).{0,4}(?:演讲|辩论|征文|文艺)'],
            '省二等': [r'(?:省级|省赛).{0,4}(?:二等).{0,4}(?:演讲|辩论|征文|文艺)'],
            '省三等': [r'(?:省级|省赛).{0,4}(?:三等).{0,4}(?:演讲|辩论|征文|文艺)'],
            '省其他': [r'(?:省级|省赛).{0,4}(?:其他|优秀|参赛).{0,4}(?:演讲|辩论|征文|文艺)'],
            '校一等': [r'(?:校级|校赛).{0,4}(?:一等|特等|最高).{0,4}(?:演讲|辩论|征文|文艺)'],
            '校二等': [r'(?:校级|校赛).{0,4}(?:二等).{0,4}(?:演讲|辩论|征文|文艺)'],
            '校三等': [r'(?:校级|校赛).{0,4}(?:三等).{0,4}(?:演讲|辩论|征文|文艺)'],
            '校其他': [r'(?:校级|校赛).{0,4}(?:其他|优秀|参赛).{0,4}(?:演讲|辩论|征文|文艺)'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 10,
    },

    # 4e: 重点竞赛 vs 普通学科竞赛
    {
        'group_id': 'key_vs_ordinary_competition',
        'name': '重点竞赛vs普通学科竞赛',
        'items': [
            'A007I','A007D','A007X','A007E','A008I','A008D','A008X','A008E',
            'A009I','A009D','A009X','A009E','A010I','A010D','A010X','A010E',
            'A026','A027','A028','A030','A031','A032','A034','A035','A036',
        ],
        'id_to_label': {},
        'signals': {
            '重点赛事': [
                r'(?:互联网\+|互联网加|大挑|小挑|创青春|挑战杯|电子设计竞赛|电赛|全国大学生电子|TI杯)',
            ],
            '普通赛事': [
                r'(?:蓝桥杯|数学建模|智能车|计算机设计|软件杯|英语竞赛|英语大赛|数学竞赛|物理竞赛|化学竞赛)',
            ],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # ────────────────────────────────────────
    # 五、荣誉称号 (2组)
    # ────────────────────────────────────────

    # 5a: 优秀学生干部/团干/团员/积极分子 省/校/院三级
    {
        'group_id': 'excellent_student_honor',
        'name': '优秀学生干部/团干/团员-省校院三级',
        'items': ['M052', 'M053', 'M054'],
        'id_to_label': {'M052': '省级', 'M053': '校级', 'M054': '院级'},
        'signals': {
            '省级': [r'省级.{0,4}(?:优秀|先进|三好|标兵)', r'(?:全省|广东省).{0,4}(?:优秀|先进)'],
            '校级': [r'校级.{0,4}(?:优秀|先进|三好|标兵)', r'(?:全校|广东技术师范大学).{0,4}(?:优秀|先进)'],
            '院级': [r'院级.{0,4}(?:优秀|先进|三好)', r'(?:电信|电子与信息).{0,4}学院.{0,4}(?:优秀|先进)'],
        },
        'penalty_ambiguous': 25,
        'bonus_clear': 10,
    },

    # 5b: 军训称号
    {
        'group_id': 'military_training_title',
        'name': '军训称号',
        'items': ['M055a', 'M055b', 'M056a', 'M056b', 'M057'],
        'id_to_label': {'M055a': '先进个人', 'M055b': '优秀干部', 'M056a': '副排长', 'M056b': '副连长', 'M057': '单项奖'},
        'signals': {
            '先进个人': [r'先进个人(?!.*干部)'],
            '优秀干部': [r'优秀.{0,2}干部', r'优秀学生干部.*军训'],
            '副排长': [r'副排长'],
            '副连长': [r'副连长'],
            '单项奖': [r'单项奖', r'军训积极分子', r'军训.{0,4}积极'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 8,
    },

    # ────────────────────────────────────────
    # 六、文艺演出 (3组 — 院/校/省各一组)
    # ────────────────────────────────────────

    # 6a: 院级文艺演出
    {
        'group_id': 'college_arts_award',
        'name': '院级文艺演出奖级',
        'items': ['S019', 'S020', 'S021', 'S022'],
        'id_to_label': {'S019': '特等奖', 'S020': '一等奖', 'S021': '二等奖', 'S022': '三等奖'},
        'signals': {
            '特等奖': [r'院级.{0,4}(?:文艺|演出|节目).{0,4}特等', r'(?:院|学院).{0,4}(?:特等|特奖)'],
            '一等奖': [r'院级.{0,4}(?:文艺|演出|节目).{0,4}(?:一等|金奖)'],
            '二等奖': [r'院级.{0,4}(?:文艺|演出|节目).{0,4}(?:二等|银奖)'],
            '三等奖': [r'院级.{0,4}(?:文艺|演出|节目).{0,4}(?:三等|铜奖|其他)'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 7,
    },

    # 6b: 校级文艺演出
    {
        'group_id': 'school_arts_award',
        'name': '校级文艺演出奖级',
        'items': ['S023', 'S024', 'S025', 'S026', 'S027'],
        'id_to_label': {'S023': '特等奖', 'S024': '一等奖', 'S025': '二等奖', 'S026': '三等奖', 'S027': '表扬奖'},
        'signals': {
            '特等奖': [r'校级.{0,4}(?:文艺|演出|节目).{0,4}特等', r'校.{0,4}(?:特等|特奖)'],
            '一等奖': [r'校级.{0,4}(?:文艺|演出|节目).{0,4}(?:一等|金奖)'],
            '二等奖': [r'校级.{0,4}(?:文艺|演出|节目).{0,4}(?:二等|银奖)'],
            '三等奖': [r'校级.{0,4}(?:文艺|演出|节目).{0,4}(?:三等|铜奖)'],
            '表扬奖': [r'校级.{0,4}(?:文艺|演出|节目).{0,4}(?:表扬|鼓励|优秀)'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 10,
    },

    # 6c: 省级文艺演出
    {
        'group_id': 'province_arts_award',
        'name': '省级文艺演出奖级',
        'items': ['S028', 'S029', 'S030', 'S031', 'S032'],
        'id_to_label': {'S028': '特等奖', 'S029': '一等奖', 'S030': '二等奖', 'S031': '三等奖', 'S032': '表扬奖'},
        'signals': {
            '特等奖': [r'省级.{0,4}(?:文艺|演出|节目).{0,4}特等', r'(?:省|高校).{0,4}(?:特等|特奖)'],
            '一等奖': [r'省级.{0,4}(?:文艺|演出|节目).{0,4}(?:一等|金奖)'],
            '二等奖': [r'省级.{0,4}(?:文艺|演出|节目).{0,4}(?:二等|银奖)'],
            '三等奖': [r'省级.{0,4}(?:文艺|演出|节目).{0,4}(?:三等|铜奖)'],
            '表扬奖': [r'省级.{0,4}(?:文艺|演出|节目).{0,4}(?:表扬|鼓励|优秀)'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 10,
    },

    # ────────────────────────────────────────
    # 七、体育竞赛 (3组)
    # ────────────────────────────────────────

    # 7a: 院运会名次分界
    {
        'group_id': 'college_sports_rank',
        'name': '院运会名次',
        'items': ['S001', 'S002', 'S003', 'S004', 'S005'],
        'id_to_label': {'S001': '参赛者', 'S002': '裁判员', 'S003': '4-6名', 'S004': '前三名', 'S005': '破纪录'},
        'signals': {
            '参赛者': [r'(?:参加|参赛).{0,4}(?:院运会|院运动)', r'院运会.{0,4}(?:参加|参赛)'],
            '裁判员': [r'裁判'],
            '4-6名': [r'(?:第\s*[456]|4-6)名', r'(?:四|五|六)等奖'],
            '前三名': [r'(?:第\s*[123]|前三)名', r'(?:冠军|亚军|季军|一|二|三)等奖'],
            '破纪录': [r'破(?:院)?记录'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 7b: 校运会名次分界
    {
        'group_id': 'school_sports_rank',
        'name': '校运会名次',
        'items': ['S007', 'S008', 'S009', 'S010', 'S011'],
        'id_to_label': {'S007': '参赛者', 'S008': '裁判员', 'S009': '前三名', 'S010': '4-8名', 'S011': '破纪录'},
        'signals': {
            '参赛者': [r'(?:参加|参赛).{0,4}(?:校运会|校运动)'],
            '裁判员': [r'裁判'],
            '前三名': [r'(?:第\s*[123]|前三)名', r'(?:冠军|亚军|季军).{0,4}(?:校|运动)'],
            '4-8名': [r'(?:第\s*[45678]|4-8)名'],
            '破纪录': [r'破(?:校)?记录'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 8,
    },

    # 7c: 省/国家级运动会
    {
        'group_id': 'province_national_sports',
        'name': '省/国家级运动会(参加/名次/破纪录)',
        'items': ['S013','S014','S015','S016','S017','S018'],
        'id_to_label': {'S013':'省参加','S014':'省名次','S015':'省破纪录','S016':'国参加','S017':'国名次','S018':'国破纪录'},
        'signals': {
            '省参加': [r'(?:省级|省|市).{0,4}(?:运动会|大运会).{0,4}(?:参加|参赛)'],
            '省名次': [r'(?:省级|省|市).{0,4}(?:运动会|大运会).{0,4}(?:获得|获得名次|第.{0,2}名)'],
            '省破纪录': [r'(?:省级|省|市).{0,4}(?:运动会|大运会).{0,4}破纪录'],
            '国参加': [r'(?:全国|国家级).{0,4}(?:运动会|大运会|全运).{0,4}(?:参加|参赛)'],
            '国名次': [r'(?:全国|国家级).{0,4}(?:运动会|大运会|全运).{0,4}(?:获得|名次|第.{0,2}名)'],
            '国破纪录': [r'(?:全国|国家级).{0,4}(?:运动会|大运会|全运).{0,4}破纪录'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 8,
    },

    # ────────────────────────────────────────
    # 八、论文/专利/立项 (5组)
    # ────────────────────────────────────────

    # 8a: 大创 国家级/省级/校级
    {
        'group_id': 'dachuang_level',
        'name': '大创立项级别',
        'items': ['A022', 'A023', 'A024', 'A025'],
        'id_to_label': {'A022': '国重点', 'A023': '国普通', 'A024': '省', 'A025': '校'},
        'signals': {
            '国重点': [r'(?:国家级|全国).{0,4}(?:重点|大创).{0,4}(?:立项|结项)', r'大创.{0,4}国家级重点'],
            '国普通': [r'(?:国家级|全国).{0,4}(?:普通|大创)(?!.*重点).{0,4}(?:立项|结项)'],
            '省': [r'(?:省级|省).{0,4}大创.{0,4}(?:立项|结项)', r'大创.{0,4}省级'],
            '校': [r'(?:校级|校).{0,4}大创.{0,4}(?:立项|结项)', r'大创.{0,4}校级'],
        },
        'penalty_ambiguous': 25,
        'bonus_clear': 12,
    },

    # 8b: 攀登计划 国/省/校
    {
        'group_id': 'pandeng_level',
        'name': '攀登计划级别',
        'items': ['A018', 'A019', 'A020', 'A021'],
        'id_to_label': {'A018': '国负责人', 'A019': '国核心', 'A020': '省', 'A021': '校'},
        'signals': {
            '国负责人': [r'攀登计划.{0,4}(?:国家级|全国).{0,4}(?:负责人|主持)'],
            '国核心': [r'攀登计划.{0,4}(?:国家级|全国).{0,4}(?:成员|核心|2-3名)'],
            '省': [r'攀登计划.{0,4}(?:省级|省)'],
            '校': [r'攀登计划.{0,4}(?:校级|校)'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 10,
    },

    # 8c-8d: 专利类型+授权/申请
    {
        'group_id': 'patent_type_and_stage',
        'name': '专利类型(发明/新型/外观/软著)与阶段(授权/申请)',
        'items': ['A065','A066','A067','A068','A069','A070','A071'],
        'id_to_label': {
            'A065':'发明授权','A066':'新型授权','A067':'软著授权',
            'A068':'外观授权','A069':'发明申请','A070':'新型申请','A071':'外观申请',
        },
        'signals': {
            '发明授权': [r'(?:发明专利|发明).{0,4}(?:授权|授予|获得|证书)(?!.*申请)'],
            '新型授权': [r'(?:实用新型|新型).{0,4}(?:授权|授予|获得|证书)(?!.*申请)'],
            '软著授权': [r'(?:软件著作权|软著|计算机软件).{0,4}(?:登记|授权|获得|证书)'],
            '外观授权': [r'(?:外观专利|外观设计).{0,4}(?:授权|授予|获得|证书)(?!.*申请)'],
            '发明申请': [r'(?:发明专利|发明).{0,4}(?:申请|受理|审查|公开)(?!.*授权)'],
            '新型申请': [r'(?:实用新型|新型).{0,4}(?:申请|受理|审查)(?!.*授权)'],
            '外观申请': [r'(?:外观专利|外观设计).{0,4}(?:申请|受理|审查)(?!.*授权)'],
        },
        'penalty_ambiguous': 30,
        'bonus_clear': 12,
    },

    # 8e: 论文级别 SCI/核心/国/省
    {
        'group_id': 'paper_level',
        'name': '论文级别(SCI/核心/国家级/省级)',
        'items': ['A062','A063','A001','A002','A003'],
        'id_to_label': {'A062':'SCI','A063':'核心/EI','A001':'国家级','A002':'省级','A003':'校级'},
        'signals': {
            'SCI': [r'SCI', r'Science', r'Nature', r'中科院.{0,2}区'],
            '核心/EI': [r'核心期刊', r'EI', r'CSSCI', r'北大核心', r'南大核心'],
            '国家级': [r'(?:国家级|全国).{0,4}(?:学术|论文|会议)(?!.*(?:SCI|核心|EI))'],
            '省级': [r'(?:省级|省).{0,4}(?:学术|论文|会议)'],
            '校级': [r'(?:校级|校).{0,4}(?:学术|论文|会议)'],
        },
        'penalty_ambiguous': 28,
        'bonus_clear': 12,
    },

    # ────────────────────────────────────────
    # 九、文明宿舍 (已在上面的3c组中)
    # ────────────────────────────────────────

    # ────────────────────────────────────────
    # 十、其他零散 (7组)
    # ────────────────────────────────────────

    # 10a: 考研 参加/考上
    {
        'group_id': 'postgraduate_exam',
        'name': '考研参加/考上',
        'items': ['A060', 'A061'],
        'id_to_label': {'A060': '参加考试', 'A061': '成功考上'},
        'signals': {
            '参加考试': [r'(?:参加|报名).{0,4}(?:研究生|考研|硕士)', r'(?:考研|研究生).{0,4}(?:参加|报名|初试|复试)'],
            '成功考上': [r'(?:考上|录取|上岸|通过|考入).{0,4}(?:研究生|硕士)', r'(?:录取通知书|拟录取|预录取)'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 10,
    },

    # 10b: 三下乡 参加/校级奖/省级奖
    {
        'group_id': 'sanxiaxiang_level',
        'name': '三下乡参加/获奖级别',
        'items': ['M049', 'M050', 'M051'],
        'id_to_label': {'M049': '参加', 'M050': '校级奖', 'M051': '省级奖'},
        'signals': {
            '参加': [r'(?:三下乡|下乡|社会实践)(?!.*(?:获|奖|表彰))'],
            '校级奖': [r'(?:三下乡|下乡).{0,4}(?:校级|校)(?:.*(?:奖|表彰))'],
            '省级奖': [r'(?:三下乡|下乡).{0,4}(?:省级|省)(?:.*(?:奖|表彰))'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 10,
    },

    # 10c: 双学位/辅修
    {
        'group_id': 'dual_degree',
        'name': '双学位/辅修',
        'items': ['A054', 'A055'],
        'id_to_label': {'A054': '双学位', 'A055': '辅修'},
        'signals': {
            '双学位': [r'双学位', r'第二学位', r'双学士'],
            '辅修': [r'(?:辅修|第二专业|副修)(?!.*(?:双学位|学位|学士))'],
        },
        'penalty_ambiguous': 15,
        'bonus_clear': 7,
    },

    # 10d: 学业均分三档
    {
        'group_id': 'gpa_tier',
        'name': '学业均分三档(85/80/75)',
        'items': ['A057', 'A058', 'A059'],
        'id_to_label': {'A057': '≥85', 'A058': '≥80', 'A059': '≥75'},
        'signals': {
            '≥85': [r'(?:均分|平均分|成绩|GPA).{0,4}(?:8[5-9]|9\d|100)', r'85分以上'],
            '≥80': [r'(?:均分|平均分|成绩|GPA).{0,4}(?:8[0-4])', r'80分以上'],
            '≥75': [r'(?:均分|平均分|成绩|GPA).{0,4}(?:7[5-9])', r'75分以上'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 8,
    },

    # 10e: 班集体获奖 省/校×班长/前5/普通
    {
        'group_id': 'class_award_role',
        'name': '班集体获奖角色',
        'items': ['M078','M079','M080','M081','M082'],
        'id_to_label': {'M078':'省班长','M079':'省团员','M080':'校班长','M081':'校前5','M082':'校团员'},
        'signals': {
            '省班长': [r'(?:省级|省).{0,4}(?:班集体|班级).{0,4}(?:班长|团支书|表彰)'],
            '省团员': [r'(?:省级|省).{0,4}(?:班集体|班级).{0,4}(?:团员|学生)(?!.*(?:班长|团支书))'],
            '校班长': [r'(?:校级|校).{0,4}(?:班集体|班级).{0,4}(?:班长|团支书|表彰)'],
            '校前5': [r'(?:校级|校).{0,4}(?:班集体|班级).{0,4}(?:前5|团员.*前)'],
            '校团员': [r'(?:校级|校).{0,4}(?:班集体|班级).{0,4}(?:团员|学生)(?!.*(?:班长|前5))'],
        },
        'penalty_ambiguous': 22,
        'bonus_clear': 8,
    },

    # 10f: 代表大会 国/省/市/校院
    {
        'group_id': 'congress_level',
        'name': '代表大会级别',
        'items': ['M074', 'M075', 'M076', 'M077'],
        'id_to_label': {'M074': '国家级', 'M075': '省级', 'M076': '市级', 'M077': '校/院级'},
        'signals': {
            '国家级': [r'(?:国家级|全国).{0,4}(?:代表大会|团代会|学代会)'],
            '省级': [r'(?:省级|省).{0,4}(?:代表大会|团代会|学代会)'],
            '市级': [r'(?:市级|市|区).{0,4}(?:代表大会|团代会|学代会)'],
            '校/院级': [r'(?:校级|院级|校|院).{0,4}(?:团代会|学代会|代表大会)'],
        },
        'penalty_ambiguous': 20,
        'bonus_clear': 8,
    },

    # 10g: 献血
    {
        'group_id': 'blood_donation_type',
        'name': '献血(无偿献血 vs 献血先进个人)',
        'items': ['M063', 'M060'],
        'id_to_label': {'M063': '无偿献血', 'M060': '献血先进个人'},
        'signals': {
            '无偿献血': [r'(?:献血|无偿献血|献血证)(?!.*(?:先进|表彰|荣誉|个人))'],
            '献血先进个人': [r'献血.{0,4}(?:先进|表彰|荣誉|个人|标兵)'],
        },
        'penalty_ambiguous': 18,
        'bonus_clear': 8,
    },

    # 10h: 社团层级
    {
        'group_id': 'club_hierarchy',
        'name': '社团会长/部长/干事',
        'items': ['M037', 'M038', 'M039'],
        'id_to_label': {'M037': '会长', 'M038': '正副部长', 'M039': '干事'},
        'signals': {
            '会长': [r'(?:社团|协会).{0,3}(?:会长|社长|负责人|主席)'],
            '正副部长': [r'(?:社团|协会).{0,3}(?:部长|副部长)'],
            '干事': [r'(?:社团|协会).{0,3}(?:干事|成员|部员)'],
        },
        'penalty_ambiguous': 16,
        'bonus_clear': 6,
    },
]


# ══════════════════════════════════════════
# 2. 混淆组索引构建
# ══════════════════════════════════════════

def _build_group_index():
    """构建 item_id → [group_index] 的快速索引"""
    index = {}
    for gi, group in enumerate(CONFUSION_GROUPS):
        for item_id in group['items']:
            if item_id not in index:
                index[item_id] = []
            index[item_id].append(gi)
    return index


ITEM_GROUP_INDEX = _build_group_index()


# ══════════════════════════════════════════
# 3. 区分信号检测
# ══════════════════════════════════════════

def _detect_signals(text: str, signals: dict) -> set:
    """检测文本中包含哪些区分信号"""
    detected = set()
    for label, patterns in signals.items():
        for pattern in patterns:
            try:
                if re.search(pattern, text):
                    detected.add(label)
                    break
            except re.error:
                if pattern in text:
                    detected.add(label)
    return detected


def _resolve_four_key_competitions(match_id: str, detected_signals: set, text: str) -> tuple[str, float]:
    """专门处理四大赛事(I/D/X/E) + 奖级的复杂映射"""
    # 提取 id 中的赛事类型和奖级信息
    # ID 格式: A{NNN}{X} 其中 X = I/D/X/E (赛事类型), NNN = 奖级编号
    id_str = match_id

    # 赛事类型检测
    sub_signals = None
    for g in CONFUSION_GROUPS:
        if g['group_id'] == 'four_key_competitions_prize':
            sub_signals = g.get('sub_signals', {})
            break

    if sub_signals:
        for comp_type, patterns in sub_signals.items():
            for pat in patterns:
                try:
                    if re.search(pat, text):
                        # 材料明确提到该赛事类型
                        # 检查 match_id 是否匹配
                        if comp_type == '互联网+' and 'I' in id_str:
                            return ('match', 0)
                        elif comp_type == '大挑' and 'D' in id_str:
                            return ('match', 0)
                        elif comp_type == '小挑' and 'X' in id_str:
                            return ('match', 0)
                        elif comp_type == '电子设计' and 'E' in id_str:
                            return ('match', 0)
                        else:
                            return ('mismatch_type', -15)  # 赛事类型不匹配
                except re.error:
                    pass

    return ('ambiguous', 0)


# ══════════════════════════════════════════
# 4. 核心混淆解析函数
# ══════════════════════════════════════════

def resolve_confusion(matches: list[dict], extracted_text: str) -> list[dict]:
    """对匹配结果进行混淆项精细化区分

    Args:
        matches: 当前所有匹配结果，每个包含 'id', 'confidence' 等字段
        extracted_text: OCR提取的文本(含文件名+extra_keyword)

    Returns:
        调整后的 matches，每个匹配项新增:
            - confusion_resolved: bool
            - confusion_group: str | None
            - confusion_adjustment: float (置信度调整值)
            - confusion_reason: str
    """
    text = extracted_text or ''

    # Step 1: 按混淆组分组匹配项
    groups_hit = {}  # group_index → [match_indices]
    for mi, m in enumerate(matches):
        item_id = m.get('id', '')
        if item_id in ITEM_GROUP_INDEX:
            for gi in ITEM_GROUP_INDEX[item_id]:
                if gi not in groups_hit:
                    groups_hit[gi] = []
                groups_hit[gi].append(mi)

    # Step 2: 对每个命中的混淆组进行区分
    for gi, match_indices in groups_hit.items():
        if len(match_indices) < 1:
            continue

        group = CONFUSION_GROUPS[gi]
        signals = group.get('signals', {})
        detected = _detect_signals(text, signals)

        # 获取该组内所有匹配的 label
        id_to_label = group.get('id_to_label', {})
        group_matches = [matches[i] for i in match_indices]

        # Step 2a: 四大赛事特殊处理
        if group['group_id'] == 'four_key_competitions_prize':
            _resolve_four_key_group(matches, match_indices, text, group, detected, id_to_label)
            continue

        # Step 2b: 通用区分逻辑
        _resolve_generic_group(matches, match_indices, text, group, detected, id_to_label)

    return matches


def _resolve_generic_group(matches, match_indices, text, group, detected_signals, id_to_label):
    """通用混淆组区分逻辑"""
    penalty = group.get('penalty_ambiguous', 20)
    bonus = group.get('bonus_clear', 8)

    # 只有一个该组匹配 → 检查是否有区分信号
    if len(match_indices) == 1:
        mi = match_indices[0]
        m = matches[mi]
        item_id = m.get('id', '')
        label = id_to_label.get(item_id, '')

        # 有明确区分信号指向这个 item → 奖励
        if label and label in detected_signals:
            m['confusion_resolved'] = True
            m['confusion_group'] = group.get('name', '')
            m['confusion_adjustment'] = bonus
            m['confusion_reason'] = f'混淆组"{group["name"]}"中明确区分→{label}，+{bonus}%'
            m['confidence'] = min(98, m['confidence'] + bonus)
        else:
            m['confusion_resolved'] = False
            m['confusion_group'] = group.get('name', '')
            m['confusion_adjustment'] = 0
            m['confusion_reason'] = f'混淆组"{group["name"]}"无明确区分信号，保持原置信'
        return

    # 多个同组匹配 → 检查是否能区分
    found_clear = False
    for mi in match_indices:
        m = matches[mi]
        item_id = m.get('id', '')
        label = id_to_label.get(item_id, '')
        m['confusion_group'] = group.get('name', '')

        if label and label in detected_signals:
            # 这个 item 有明确区分信号 → 奖励
            m['confusion_resolved'] = True
            m['confusion_adjustment'] = bonus
            m['confusion_reason'] = (
                f'混淆组"{group["name"]}"中明确区分→{label}，+{bonus}%'
            )
            m['confidence'] = min(98, m['confidence'] + bonus)
            found_clear = True
        else:
            # 无区分信号 → 惩罚
            m['confusion_resolved'] = False
            m['confusion_adjustment'] = -penalty
            m['confusion_reason'] = (
                f'混淆组"{group["name"]}"({len(match_indices)}个同组匹配)无区分信号，-{penalty}%'
            )
            m['confidence'] = max(5, m['confidence'] - penalty)

    # 如果组内有明确匹配，对同组其他模糊项额外惩罚
    if found_clear:
        for mi in match_indices:
            m = matches[mi]
            if not m.get('confusion_resolved'):
                extra_penalty = penalty // 2
                m['confusion_adjustment'] = -(penalty + extra_penalty)
                m['confusion_reason'] += f'(组内已有明确匹配，额外-{extra_penalty}%)'
                m['confidence'] = max(5, m['confidence'] - extra_penalty)


def _resolve_four_key_group(matches, match_indices, text, group, detected_signals, id_to_label):
    """四大赛事组特殊处理 — 需要区分赛事类型(I/D/X/E)和奖级"""
    penalty = group.get('penalty_ambiguous', 25)
    bonus = group.get('bonus_clear', 12)
    sub_signals = group.get('sub_signals', {})

    # 检测赛事类型
    detected_comp_type = None
    for comp_type, patterns in sub_signals.items():
        for pat in patterns:
            try:
                if re.search(pat, text):
                    detected_comp_type = comp_type
                    break
            except re.error:
                pass
        if detected_comp_type:
            break

    # 映射: 赛事类型 → id后缀
    type_suffix = {'互联网+': 'I', '大挑': 'D', '小挑': 'X', '电子设计': 'E'}

    for mi in match_indices:
        m = matches[mi]
        item_id = m.get('id', '')
        m['confusion_group'] = group.get('name', '')

        # 检查赛事类型匹配
        if detected_comp_type and len(item_id) >= 2:
            expected_suffix = type_suffix.get(detected_comp_type, '')
            actual_suffix = ''.join(c for c in item_id if c in 'IDXE')
            if actual_suffix and expected_suffix and actual_suffix != expected_suffix:
                # 赛事类型不匹配 → 重罚
                m['confusion_resolved'] = False
                m['confusion_adjustment'] = -(penalty + 10)
                m['confusion_reason'] = (
                    f'四大赛事混淆: 材料明确为"{detected_comp_type}"，但匹配到其他赛事类型，-{penalty+10}%'
                )
                m['confidence'] = max(5, m['confidence'] - penalty - 10)
                continue

        # 检查奖级信号
        label = id_to_label.get(item_id, '')
        if not label and len(item_id) >= 3:
            # 动态推断奖级
            # A007-A011=国家级, A012-A014=校级, A015-A017=院级
            # A007/A008=最高, A009=次级, A010=三等, A011=参赛
            num_part = ''.join(c for c in item_id if c.isdigit())
            if len(num_part) >= 3:
                level_code = int(num_part)
                if level_code <= 7: label = '国最高'
                elif level_code == 8: label = '省最高'
                elif level_code == 9: label = '省次级'
                elif level_code == 10: label = '省三等'
                elif level_code == 11: label = '省参赛'
                elif level_code <= 14: label = '校' + {12:'最高',13:'次级',14:'三等'}.get(level_code%100,'')
                else: label = '院' + {15:'最高',16:'次级',17:'三等'}.get(level_code%100,'')

        if label and label in detected_signals:
            m['confusion_resolved'] = True
            m['confusion_adjustment'] = bonus
            m['confusion_reason'] = f'四大赛事混淆: 明确区分→{label}，+{bonus}%'
            m['confidence'] = min(98, m['confidence'] + bonus)
        else:
            m['confusion_resolved'] = False
            m['confusion_adjustment'] = -penalty
            m['confusion_reason'] = (
                f'四大赛事混淆({len(match_indices)}个同组匹配): 无明确区分信号，-{penalty}%'
            )
            m['confidence'] = max(5, m['confidence'] - penalty)


# ══════════════════════════════════════════
# 5. 便捷入口函数
# ══════════════════════════════════════════

def apply_confusion_resolution(matches: list[dict], extracted_text: str) -> list[dict]:
    """对匹配结果应用混淆项区分（推荐入口）

    在 _score_confidence 之后、校准之前调用
    """
    if not matches:
        return matches

    # 初始化混淆字段
    for m in matches:
        m['confusion_resolved'] = False
        m['confusion_group'] = None
        m['confusion_adjustment'] = 0.0
        m['confusion_reason'] = ''

    return resolve_confusion(matches, extracted_text)


def get_confusion_audit_summary(matches: list[dict]) -> dict:
    """生成混淆项审计摘要"""
    groups_affected = set()
    total_penalty = 0.0
    total_bonus = 0.0

    for m in matches:
        if m.get('confusion_group'):
            groups_affected.add(m['confusion_group'])
            adj = m.get('confusion_adjustment', 0)
            if adj > 0:
                total_bonus += adj
            else:
                total_penalty += abs(adj)

    return {
        'total_confusion_groups': len(groups_affected),
        'groups_affected': list(groups_affected),
        'total_penalty_applied': round(total_penalty, 1),
        'total_bonus_applied': round(total_bonus, 1),
        'net_adjustment': round(total_bonus - total_penalty, 1),
    }
