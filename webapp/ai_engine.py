"""
综测智能识别引擎 v3 — 精准OCR + 自定义LLM匹配(工具调用)
"""
import re, os, json, hashlib, tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# ══════════════════════════════════════════
# OCR Engine
# ══════════════════════════════════════════
_ocr = None
_paddle_ocr = None
_rapid_ocr = None

def _get_ocr():
    global _ocr
    if _ocr is None:
        try:
            from easyocr import Reader
            _ocr = Reader(['ch_sim', 'en'], gpu=False)
        except Exception:
            _ocr = False
    return _ocr


def _get_paddle_ocr():
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(
                lang='ch',
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except Exception:
            _paddle_ocr = False
    return _paddle_ocr


def _get_rapid_ocr():
    global _rapid_ocr
    if _rapid_ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr = RapidOCR()
        except Exception:
            _rapid_ocr = False
    return _rapid_ocr


def _collect_ocr_texts(value, min_confidence: float = 0.5) -> list:
    """Normalize EasyOCR/PaddleOCR result shapes into a flat text list."""
    texts = []

    def add_text(text, conf=None):
        if text and (conf is None or conf >= min_confidence):
            texts.append(str(text))

    def walk(node):
        if node is None:
            return
        if isinstance(node, str):
            add_text(node)
            return
        if isinstance(node, dict):
            rec_texts = node.get('rec_texts')
            rec_scores = node.get('rec_scores') or []
            if isinstance(rec_texts, list):
                for idx, text in enumerate(rec_texts):
                    conf = rec_scores[idx] if idx < len(rec_scores) else None
                    add_text(text, conf)
                return
            for key in ('text', 'transcription', 'label'):
                if isinstance(node.get(key), str):
                    add_text(node[key], node.get('confidence') or node.get('score'))
            for child in node.values():
                if isinstance(child, (dict, list, tuple)):
                    walk(child)
            return
        for attr in ('json', 'res'):
            if hasattr(node, attr):
                try:
                    walk(getattr(node, attr))
                    return
                except Exception:
                    pass
        if hasattr(node, 'to_dict'):
            try:
                walk(node.to_dict())
                return
            except Exception:
                pass
        if isinstance(node, (list, tuple)):
            # RapidOCR shape: [box, text, confidence]
            if len(node) >= 3 and isinstance(node[1], str) and isinstance(node[2], (int, float)):
                add_text(node[1], node[2])
                return
            # PaddleOCR v2 shape: [box, (text, confidence)]
            if len(node) >= 2 and isinstance(node[1], (list, tuple)) and len(node[1]) >= 2:
                text, conf = node[1][0], node[1][1]
                if isinstance(text, str) and isinstance(conf, (int, float)):
                    add_text(text, conf)
                    return
            for child in node:
                walk(child)

    walk(value)
    return texts

# ══════════════════════════════════════════
# Custom LLM Client (替代 Claude)
# ══════════════════════════════════════════
_llm_available = None

def _get_llm():
    """检测自定义 LLM 是否可用"""
    global _llm_available
    if _llm_available is None:
        import config
        if config.LLM_API_KEY and config.LLM_BASE_URL:
            _llm_available = True
        else:
            _llm_available = False
    return _llm_available

# ══════════════════════════════════════════
# Text Extraction
# ══════════════════════════════════════════
def _normalize_text(text: str) -> str:
    """Clean OCR text while preserving Chinese, English, digits, and audit punctuation."""
    text = re.sub(r'\s+', ' ', text or '')
    text = text.replace('?', '(').replace('?', ')').replace('?', ':').replace('?', ',')
    text = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9\s\(\)\[\],.?:;?\-+/=<>%#_]', '', text)
    return text.strip()

def extract_text_from_image(file_path: str) -> str:
    """OCR识别图片文字 — EasyOCR / PaddleOCR / RapidOCR 逐级降级
    使用PIL读取图片为numpy数组，绕过OpenCV不支持中文路径的问题"""
    # PIL读取图片为numpy数组（PIL支持中文路径，OpenCV不支持）
    try:
        from PIL import Image
        import numpy as np
        img = Image.open(file_path).convert('RGB')
        img_array = np.array(img)
    except Exception:
        return ''

    lines = []
    ocr = _get_ocr()
    try:
        # EasyOCR
        if ocr and hasattr(ocr, 'readtext'):
            result = ocr.readtext(img_array)
            for _, text, conf in result:
                if text and conf > 0.5:
                    lines.append(text)
    except Exception:
        pass

    if not lines:
        rapid = _get_rapid_ocr()
        if rapid:
            try:
                result, _ = rapid(file_path)
                lines.extend(_collect_ocr_texts(result))
            except Exception:
                pass

    if not lines:
        paddle = _get_paddle_ocr()
        try:
            if paddle and hasattr(paddle, 'predict'):
                result = paddle.predict(img_array)
                lines.extend(_collect_ocr_texts(result))
            elif paddle and hasattr(paddle, 'ocr'):
                result = paddle.ocr(img_array)
                lines.extend(_collect_ocr_texts(result))
        except Exception:
            pass

    return _normalize_text('\n'.join(lines))

def extract_text_from_pdf(file_path: str) -> str:
    """PDF文字提取 — PyMuPDF → PyPDF2 → pdfplumber → page OCR"""
    text_parts = []
    # PyMuPDF
    try:
        import fitz
        doc = fitz.open(file_path)
        for page in doc:
            t = page.get_text()
            if t.strip():
                text_parts.append(t.strip())
            # 也尝试提取嵌入图片的文字
            for img_info in page.get_image_info():
                try:
                    xref = img_info['xref']
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n < 5:
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                        img_path = tmp.name
                        tmp.close()
                        pix.save(img_path)
                        img_text = extract_text_from_image(img_path)
                        if img_text:
                            text_parts.append(img_text)
                        try: os.remove(img_path)
                        except: pass
                except: pass
        doc.close()
        normalized = _normalize_text('\n'.join(text_parts))
        if len(normalized) >= 120:
            return normalized
    except: pass

    # PyPDF2
    try:
        from PyPDF2 import PdfReader
        for page in PdfReader(file_path).pages:
            t = page.extract_text()
            if t and t.strip():
                text_parts.append(t.strip())
        if text_parts:
            return _normalize_text('\n'.join(text_parts))
    except: pass

    # pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t and t.strip():
                    text_parts.append(t.strip())
        normalized = _normalize_text('\n'.join(text_parts))
        if len(normalized) >= 120:
            return normalized
    except: pass

    # 扫描版 PDF / 截图型 PDF：逐页渲染成图片再 OCR
    try:
        import fitz
        doc = fitz.open(file_path)
        for page in doc:
            tmp_path = None
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                tmp_path = tmp.name
                tmp.close()
                pix.save(tmp_path)
                img_text = extract_text_from_image(tmp_path)
                if img_text:
                    text_parts.append(img_text)
            finally:
                if tmp_path:
                    try: os.remove(tmp_path)
                    except: pass
        doc.close()
        normalized = _normalize_text('\n'.join(text_parts))
        if len(normalized) >= 120:
            return normalized
    except: pass

    return ''

def extract_text_from_docx(file_path: str) -> str:
    """DOCX文字提取"""
    try:
        from docx import Document
        text_parts = []
        for para in Document(file_path).paragraphs:
            if para.text.strip():
                text_parts.append(para.text.strip())
        for table in Document(file_path).tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    text_parts.append(' | '.join(row_texts))
        return _normalize_text('\n'.join(text_parts))
    except: return ''

def extract_text_from_file(file_path: str, file_type: str) -> str:
    """统一入口"""
    ext = Path(file_path).suffix.lower()
    if ext in ('.jpg','.jpeg','.png','.bmp','.gif','.webp','.tiff'):
        return extract_text_from_image(file_path)
    elif ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ('.docx','.doc'):
        return extract_text_from_docx(file_path)
    else:
        return extract_text_from_image(file_path)

# ══════════════════════════════════════════
# Fuzzy Matching
# ══════════════════════════════════════════
def _fuzzy_similarity(a: str, b: str) -> float:
    """计算两个字符串的模糊相似度 (0~1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def _contains_any_fuzzy(text: str, keywords: list, threshold: float = 0.65) -> list:
    """检查文本是否模糊包含关键词，返回匹配到的词列表"""
    matched = []
    for kw in keywords:
        def exact_hit() -> bool:
            if kw.endswith('委员'):
                return re.search(re.escape(kw) + r'(?!会)', text) is not None
            return kw in text

        if re.search(r'HC(?:IA|IP|IE)', kw, re.I):
            if kw.upper().replace(' ', '') in text.upper().replace(' ', ''):
                matched.append(kw)
            continue
        if re.fullmatch(r'[A-Za-z0-9-]+', kw) and len(kw) <= 8:
            if kw.upper() in text.upper():
                matched.append(kw)
            continue
        if len(kw) <= 4:
            # 短词精确匹配
            if exact_hit():
                matched.append(kw)
        else:
            # 长词先精确再模糊
            if exact_hit():
                matched.append(kw)
            else:
                # 滑动窗口模糊匹配
                kw_len = len(kw)
                text_clean = text.replace(' ', '')
                for i in range(len(text_clean) - kw_len + 1):
                    window = text_clean[i:i + kw_len]
                    if _fuzzy_similarity(window, kw) >= threshold:
                        matched.append(kw)
                        break
    return matched

# ══════════════════════════════════════════
# Keyword Database
# ══════════════════════════════════════════
ITEM_SIGNATURES = {
    # ── 品德: 学生干部 ──
    'M001': {'keywords':['学生会主席','主席团','校学生会正职','学生会负责人','学生会主席团正式成员'],'boost':10},
    'M002': {'keywords':['学生会副主席','学生会副职','主席团副职','校学生会主席团副职'],'boost':9},
    'M003': {'keywords':['学生会部长','部长正职','校会部长','校学生会部长正职'],'boost':7},
    'M004': {'keywords':['学生会副部长','校学生会部长副职'],'boost':6},
    'M005': {'keywords':['学生会干事','校会干事','学生会成员','校学生会干事满一年'],'boost':5},
    'M006': {'keywords':['社联','社团联合会','校学生社团联合会主席团','校社联'],'boost':9},
    'M007a': {'keywords':['社联部长','社团联合会部长','校社联部长','校学生社团联合会部长'],'boost':6},
    'M007b': {'keywords':['社联干事','社团联合会干事','校社联干事','校学生社团联合会干事'],'boost':4},
    'M008': {'keywords':['青年志愿者协会主席团','校青协主席团','青协主席团'],'boost':10},
    'M009a': {'keywords':['青年志愿者协会部长','青协部长','校青协部长'],'boost':6},
    'M009b': {'keywords':['青年志愿者协会干事','青协干事','校青协干事'],'boost':4},
    'M010': {'keywords':['红十字会主席团','校红会主席团'],'boost':10},
    'M011a': {'keywords':['自律委员会主席团','校自律委员会主席团'],'boost':6},
    'M011b': {'keywords':['自律委员会部长','校自律委员会部长'],'boost':4},
    'M011c': {'keywords':['自律委员会干事','校自律委员会干事'],'boost':3},
    'M012a': {'keywords':['勤工助学中心主席团','勤工助学中心','校勤工助学'],'boost':9},
    'M012b': {'keywords':['勤工助学中心部长','校勤工助学部长'],'boost':6},
    'M012c': {'keywords':['广播站主席团','校广播站主席团','校广播站'],'boost':9},
    'M012d': {'keywords':['广播站部长','校广播站部长'],'boost':6},
    'M013a': {'keywords':['艺术团主席团','校艺术团主席团'],'boost':9},
    'M013b': {'keywords':['艺术团分团长','校艺术团分团团长','校艺术团分团长'],'boost':6},
    'M014a': {'keywords':['国旗护卫队队长','国旗护卫队队长职务'],'boost':6},
    'M014b': {'keywords':['国旗护卫队部长','国旗护卫队部长职务'],'boost':4},
    'M014c': {'keywords':['国旗护卫队队员','国旗护卫队队员职务','国旗队'],'boost':3},
    'M015': {'keywords':['编辑部','广师大学生','责编'],'boost':5},
    'M016a': {'keywords':['辩论队队长','校辩论队队长'],'boost':5},
    'M016b': {'keywords':['辩论队队员','校辩论队队员'],'boost':3},
    'M017': {'keywords':['工作助理','学生处助理','校团委工作助理'],'boost':8},
    'M018': {'keywords':['广师视频','广师视频成员','校园电视台'],'boost':6},
    'M019': {'keywords':['院学生会主席','团总支副书记','院主席团','院团总支学生会主席'],'boost':10},
    'M020': {'keywords':['院学生会部长','院部长','院团总支学生会部长'],'boost':7},
    'M021': {'keywords':['院学生会干事','院干事','院团总支学生会干事'],'boost':5},
    'M022': {'keywords':['预干','院学生会预干','院团总支学生会预干'],'boost':3},
    'M023': {'keywords':['科技站技术部优秀','科技站考核优秀','院科技站技术部优秀'],'boost':10},
    'M024': {'keywords':['科技站技术部合格','科技站考核合格','院科技站技术部合格'],'boost':6},
    'M025a': {'keywords':['科技站秘书部部长','院科技站秘书部部长','科技站部长'],'boost':7},
    'M025b': {'keywords':['科技站秘书部成员','院科技站秘书部成员','科技站成员'],'boost':6},
    'M026a': {'keywords':['学生党支部副书记','党支部副书记','院学生党支部副书记'],'boost':6},
    'M026b': {'keywords':['学生党支部委员','党支部委员','院学生党支部委员'],'boost':5},
    'M027a': {'keywords':['医保小组组长','综测小组组长','助学贷款小组组长','心理小组组长','就业小组组长','党务小组组长','院级工作小组组长'],'boost':7},
    'M027b': {'keywords':['医保小组组员','综测小组组员','助学贷款小组组员','心理小组组员','就业小组组员','党务小组组员','院级工作小组组员'],'boost':5},
    'M028': {'keywords':['辅导员助理','辅导员助理满一年'],'boost':6},
    'M029': {'keywords':['助理班主任','助班'],'boost':6},
    'M030': {'keywords':['助部','院级助部'],'boost':4},
    'M031': {'keywords':['班长','团支书','班级班长','班级团支书'],'boost':9},
    'M032': {'keywords':['副班长','班级副班长'],'boost':7},
    'M033': {'keywords':['学习委员','班级学习委员'],'boost':7},
    'M034': {'keywords':['纪律委员','班级纪律委员'],'boost':6},
    'M035': {'keywords':['班干部','生活委员','宣传委员','组织委员','体育委员','文娱委员','心理委员','信息员','其他班干部'],'boost':5},
    'M036': {'keywords':['宿舍长','舍长','寝室长'],'boost':4},
    'M037': {'keywords':['社团会长','社团负责人'],'boost':4},
    'M038': {'keywords':['社团副部长','社团正副部长','社团部长'],'boost':3},
    'M039': {'keywords':['社团干事','社团成员'],'boost':2},

    # ── 品德: 荣誉/活动 ──
    'M040': {'keywords':['校级刊物','校级纸质刊物','刊物发表文章','校报发表'],'boost':5},
    'M041': {'keywords':['院级刊物','院级纸质刊物','院刊发表'],'boost':3},
    'M042': {'keywords':['思想教育','校级思想教育','校外思想教育','参加活动'],'boost':4},
    'M043': {'keywords':['院级思想教育','团日活动参加','院级活动参加'],'boost':4},
    'M044': {'keywords':['活动获奖','校级活动第一名','校外活动第一名','活动获奖校级第一'],'boost':5},
    'M045': {'keywords':['活动获奖第二','活动获奖第三','校级活动第二三名'],'boost':4},
    'M048': {'keywords':['志愿者','志愿活动','义务劳动','志愿服务','义工'],'boost':5},
    'M049': {'keywords':['三下乡','社会实践','暑期实践','寒假实践','下乡'],'boost':8},
    'M052': {'keywords':['省级优秀学生干部','省级优秀团干','省级优秀团员','省级积极分子','省优秀学生','省三好学生'],'boost':10},
    'M053': {'keywords':['校级优秀学生干部','优秀团干','优秀团员','积极分子','三好学生','优秀学生'],'boost':9},
    'M054': {'keywords':['院级优秀学生干部','院优秀团员','院积极分子','院三好'],'boost':7},
    'M055a': {'keywords':['军训先进个人','军训先进个人称号'],'boost':8},
    'M055b': {'keywords':['军训优秀学生干部','军训优秀干部'],'boost':8},
    'M056a': {'keywords':['军训副排长','副排长'],'boost':5},
    'M056b': {'keywords':['军训副连长','副连长','军训副连长职务'],'boost':5},
    'M058': {'keywords':['校级文体先进个人','文体先进个人校级'],'boost':6},
    'M059': {'keywords':['院级文体先进个人','文体先进个人院级'],'boost':4},
    'M060': {'keywords':['献血先进个人','献血先进'],'boost':4},
    'M061a': {'keywords':['校学生处通报表扬','学生处表扬'],'boost':4},
    'M061b': {'keywords':['校团委通报表扬','团委表扬'],'boost':4},
    'M061c': {'keywords':['校学生会通报表扬','学生会表扬'],'boost':4},
    'M062': {'keywords':['科技站学术之星','学术之星'],'boost':7},
    'M063': {'keywords':['无偿献血','献血','献血证','献血证明'],'boost':8},
    'M064': {'keywords':['见义勇为','英勇行为','见义勇为表彰'],'boost':10},
    'M066': {'keywords':['文明宿舍标兵','宿舍标兵','标兵宿舍'],'boost':9},
    'M067': {'keywords':['文明宿舍','优秀宿舍','文明寝室'],'boost':8},
    'M073a': {'keywords':['院办公室值班','院办值班','办公室值班'],'boost':3},
    'M073b': {'keywords':['党建办公室值班','党建办值班'],'boost':3},

    # ── 学业: 论文/专利 ──
    'A001': {'keywords':['国家级学术论文','全国学术会议','国家学术会议宣读','全国性学术会议'],'boost':10},
    'A002': {'keywords':['省级学术论文','省级学术会议','省学术会议'],'boost':9},
    'A003': {'keywords':['校级学术论文','学术论文发表','论文发表','校学术论文'],'boost':6},
    'A062': {'keywords':['SCI论文','SCI一区','SCI二区','中科院二区','SCI期刊','Science','Nature','SCI收录'],'boost':10},
    'A063': {'keywords':['核心期刊','EI期刊','EI收录','EI论文','国内核心','北大核心','南大核心','CSSCI'],'boost':10},
    'A065': {'keywords':['发明专利','授权发明专利','发明授权','国家发明专利'],'boost':10},
    'A066': {'keywords':['实用新型专利','实用新型授权','实用新型'],'boost':9},
    'A067': {'keywords':['软件著作权','软著','计算机软件著作权','软件版权'],'boost':9},
    'A069': {'keywords':['发明专利申请','申请发明专利','专利申请'],'boost':7},

    # ── 学业: 重点科技竞赛（互联网+ / 大挑 / 小挑 / 电子设计竞赛） ──
    # 大挑 = "挑战杯"全国大学生课外学术科技作品竞赛（学术科研/发明创作/调研报告，奇数年）
    # 小挑 = "挑战杯"中国大学生创业计划竞赛/创青春（商业创业/项目落地/商业模式，偶数年）
    # 国家级最高奖
    'A007I': {'keywords':['互联网+国家级最高奖','互联网+国赛最高奖','互联网+国家特等奖','互联网+国家一等奖','互联网+国赛特等奖','互联网+国赛一等奖','中国国际互联网+最高奖','互联网+金奖'],'boost':10},
    'A007D': {'keywords':['大挑国家级最高奖','大挑国家特等奖','大挑国家一等奖','大挑国赛特等奖','大挑国赛一等奖','挑战杯国家最高奖','大挑杯最高奖','课外学术科技作品国家最高奖'],'boost':10},
    'A007X': {'keywords':['小挑国家级最高奖','小挑国家特等奖','小挑国家一等奖','小挑国赛特等奖','小挑国赛一等奖','挑战杯创业计划国家最高奖','创业计划竞赛国家最高奖'],'boost':10},
    'A007E': {'keywords':['电子设计竞赛国家级最高奖','电子设计国赛最高奖','全国大学生电子设计最高奖','电子设计国家特等奖','电子设计国家一等奖','电赛国赛最高奖','TI杯电子设计最高奖'],'boost':10},
    # 省级最高奖
    'A008I': {'keywords':['互联网+省级最高奖','互联网+省特等奖','互联网+省一等奖','互联网+省赛最高奖','互联网+省级金奖'],'boost':10},
    'A008D': {'keywords':['大挑省级最高奖','大挑省特等奖','大挑省一等奖','大挑省赛最高奖','挑战杯省级最高奖','大挑杯省级最高奖'],'boost':10},
    'A008X': {'keywords':['小挑省级最高奖','小挑省特等奖','小挑省一等奖','小挑省赛最高奖','创业计划省级最高奖'],'boost':10},
    'A008E': {'keywords':['电子设计竞赛省级最高奖','电子设计省赛最高奖','电子设计省特等奖','电子设计省一等奖','电赛省赛最高奖'],'boost':10},
    # 省级次级奖（二等奖）
    'A009I': {'keywords':['互联网+省级二等奖','互联网+省二等奖','互联网+省赛二等奖'],'boost':9},
    'A009D': {'keywords':['大挑省级二等奖','大挑省二等奖','大挑省赛二等奖','挑战杯省级二等奖'],'boost':9},
    'A009X': {'keywords':['小挑省级二等奖','小挑省二等奖','小挑省赛二等奖','创业计划省级二等奖'],'boost':9},
    'A009E': {'keywords':['电子设计竞赛省级二等奖','电子设计省赛二等奖','电子设计省二等奖','电赛省二等奖'],'boost':9},
    # 省级三等奖
    'A010I': {'keywords':['互联网+省级三等奖','互联网+省三等奖','互联网+省赛三等奖'],'boost':8},
    'A010D': {'keywords':['大挑省级三等奖','大挑省三等奖','大挑省赛三等奖','挑战杯省级三等奖'],'boost':8},
    'A010X': {'keywords':['小挑省级三等奖','小挑省三等奖','小挑省赛三等奖','创业计划省级三等奖'],'boost':8},
    'A010E': {'keywords':['电子设计竞赛省级三等奖','电子设计省赛三等奖','电子设计省三等奖','电赛省三等奖'],'boost':8},
    # 省级参赛/四等奖
    'A011I': {'keywords':['互联网+省级参赛','互联网+省级四等奖','互联网+省级优秀奖','互联网+省赛参赛'],'boost':5},
    'A011D': {'keywords':['大挑省级参赛','大挑省级四等奖','大挑省级优秀奖','大挑省赛参赛'],'boost':5},
    'A011X': {'keywords':['小挑省级参赛','小挑省级四等奖','小挑省级优秀奖','小挑省赛参赛'],'boost':5},
    'A011E': {'keywords':['电子设计竞赛省级参赛','电子设计省级优秀奖','电赛省赛参赛'],'boost':5},
    # 校级最高奖
    'A012I': {'keywords':['互联网+校级最高奖','互联网+校特等奖','互联网+校一等奖','互联网+校赛最高奖'],'boost':7},
    'A012D': {'keywords':['大挑校级最高奖','大挑校特等奖','大挑校一等奖','大挑校赛最高奖','挑战杯校级最高奖'],'boost':7},
    'A012X': {'keywords':['小挑校级最高奖','小挑校特等奖','小挑校一等奖','小挑校赛最高奖','创业计划校级最高奖'],'boost':7},
    'A012E': {'keywords':['电子设计竞赛校级最高奖','电子设计校特等奖','电子设计校一等奖','电赛校赛最高奖'],'boost':7},
    # 校级次级奖（二等奖）
    'A013I': {'keywords':['互联网+校级二等奖','互联网+校二等奖','互联网+校赛二等奖'],'boost':6},
    'A013D': {'keywords':['大挑校级二等奖','大挑校二等奖','大挑校赛二等奖','挑战杯校级二等奖'],'boost':6},
    'A013X': {'keywords':['小挑校级二等奖','小挑校二等奖','小挑校赛二等奖'],'boost':6},
    'A013E': {'keywords':['电子设计竞赛校级二等奖','电子设计校二等奖','电赛校二等奖'],'boost':6},
    # 校级三等奖/参赛
    'A014I': {'keywords':['互联网+校级三等奖','互联网+校三等奖','互联网+校赛三等奖','互联网+校级参赛'],'boost':4},
    'A014D': {'keywords':['大挑校级三等奖','大挑校三等奖','大挑校赛三等奖','大挑杯校级参赛'],'boost':4},
    'A014X': {'keywords':['小挑校级三等奖','小挑校三等奖','小挑校赛三等奖','小挑杯校级参赛'],'boost':4},
    'A014E': {'keywords':['电子设计竞赛校级三等奖','电赛校三等奖','电子设计校赛三等奖','电子设计校级参赛'],'boost':4},
    # 院级最高奖
    'A015I': {'keywords':['互联网+院级最高奖','互联网+院一等奖','互联网+院赛最高奖'],'boost':5},
    'A015D': {'keywords':['大挑院级最高奖','大挑院一等奖','大挑院赛最高奖','挑战杯院级最高奖'],'boost':5},
    'A015X': {'keywords':['小挑院级最高奖','小挑院一等奖','小挑院赛最高奖'],'boost':5},
    'A015E': {'keywords':['电子设计竞赛院级最高奖','电子设计院一等奖','电赛院级最高奖'],'boost':5},
    # 院级次级奖（二等奖）
    'A016I': {'keywords':['互联网+院级二等奖','互联网+院二等奖','互联网+院赛二等奖'],'boost':4},
    'A016D': {'keywords':['大挑院级二等奖','大挑院二等奖','大挑院赛二等奖','挑战杯院级二等奖'],'boost':4},
    'A016X': {'keywords':['小挑院级二等奖','小挑院二等奖','小挑院赛二等奖'],'boost':4},
    'A016E': {'keywords':['电子设计竞赛院级二等奖','电子设计院二等奖','电赛院二等奖'],'boost':4},
    # 院级三等奖/参赛
    'A017I': {'keywords':['互联网+院级三等奖','互联网+院三等奖','互联网+院赛三等奖','互联网+院级参赛'],'boost':2},
    'A017D': {'keywords':['大挑院级三等奖','大挑院三等奖','大挑院赛三等奖','大挑杯院级参赛'],'boost':2},
    'A017X': {'keywords':['小挑院级三等奖','小挑院三等奖','小挑院赛三等奖','小挑杯院级参赛'],'boost':2},
    'A017E': {'keywords':['电子设计竞赛院级三等奖','电子设计院三等奖','电赛院三等奖','电赛院级参赛'],'boost':2},

    # ── 学业: 其他专业竞赛 ──
    # 国家级
    'A026': {'keywords':['其他专业竞赛国家级最高奖','蓝桥杯国家级最高奖','蓝桥杯国赛特等奖','蓝桥杯国赛一等奖','数学建模国家级最高奖','全国数学建模最高奖','智能汽车国家级最高奖','计算机设计国家级最高奖','全国大学生计算机设计最高奖'],'boost':10},
    'A027': {'keywords':['其他专业竞赛国家级二等奖','蓝桥杯国赛二等奖','数学建模国赛二等奖','智能汽车国赛二等奖','计算机设计国赛二等奖'],'boost':9},
    'A028': {'keywords':['其他专业竞赛国家级三等奖','蓝桥杯国赛三等奖','数学建模国赛三等奖','智能汽车国赛三等奖','计算机设计国赛三等奖'],'boost':8},
    'A029': {'keywords':['其他专业竞赛国家级其他奖','蓝桥杯国赛优秀奖','数学建模国赛优秀奖','智能汽车国赛优秀奖'],'boost':6},
    # 省级
    'A030': {'keywords':['其他专业竞赛省级最高奖','蓝桥杯省特等奖','蓝桥杯省一等奖','数学建模省最高奖','智能汽车省最高奖','计算机设计省最高奖','蓝桥杯省级最高奖'],'boost':8},
    'A031': {'keywords':['其他专业竞赛省级二等奖','蓝桥杯省二等奖','数学建模省赛二等奖','智能汽车省二等奖','计算机设计省二等奖'],'boost':7},
    'A032': {'keywords':['其他专业竞赛省级三等奖','蓝桥杯省三等奖','数学建模省赛三等奖','智能汽车省三等奖','计算机设计省三等奖'],'boost':6},
    'A033': {'keywords':['其他专业竞赛省级其他奖','蓝桥杯省优秀奖','数学建模省赛优秀奖'],'boost':4},
    # 校级
    'A034': {'keywords':['其他专业竞赛校级最高奖','蓝桥杯校一等奖','数学建模校赛最高奖'],'boost':5},
    'A035': {'keywords':['其他专业竞赛校级二等奖'],'boost':4},
    'A036': {'keywords':['其他专业竞赛校级三等奖'],'boost':3},
    'A037': {'keywords':['其他专业竞赛校级其他奖','其他专业竞赛校级参赛'],'boost':2},
    # 院级
    'A038': {'keywords':['其他专业竞赛院级一等奖'],'boost':3},
    'A039': {'keywords':['其他专业竞赛院级二等奖'],'boost':2},
    'A040': {'keywords':['其他专业竞赛院级三等奖'],'boost':2},
    'A041': {'keywords':['其他专业竞赛院级其他奖','其他专业竞赛院级参赛'],'boost':1},

    # ── 学业: 立项 ──
    'A018': {'keywords':['攀登计划国家级','攀登计划国家立项','国家级攀登计划'],'boost':10},
    'A020': {'keywords':['攀登计划省级','攀登计划省立项','省级攀登计划'],'boost':9},
    'A022': {'keywords':['大创国家级','国家级大创','大创国级重点','大学生创新创业国家级'],'boost':10},
    'A024': {'keywords':['大创省级','省级大创','大创省级重点','大学生创新创业省级'],'boost':9},

    # ── 学业: 证书 ──
    'A042': {'keywords':['英语四级','CET4','CET-4','四级成绩单','四级证书','四级通过','四级考试','四级425','大学英语四级','CET4成绩'],'boost':9},
    'A043': {'keywords':['英语六级','CET6','CET-6','六级成绩单','六级证书','六级通过','六级考试','六级425','大学英语六级','CET6成绩'],'boost':10},
    'A044': {'keywords':['专业技术高级','高级工程师','高级证书','高级职业资格','高级职称','HCIE','HUAWEI HCIE','华为HCIE','高级认证'],'boost':9},
    'A045': {'keywords':['专业技术中级','中级工程师','中级证书','中级职业资格','中级职称','HCIP','HUAWEI HCIP','华为HCIP','中级认证'],'boost':7},
    'A046': {'keywords':['专业技术初级','初级证书','初级职业资格','初级职称','HCIA','HCIA-AI','HUAWEI HCIA','华为HCIA','华为认证','AI认证','人工智能认证','初级认证'],'boost':5},
    'A047': {'keywords':['计算机四级','NCRE四级','计算机等级四级','全国计算机四级'],'boost':8},
    'A048': {'keywords':['计算机三级','NCRE三级','计算机等级三级','全国计算机三级'],'boost':7},
    'A049': {'keywords':['计算机二级','NCRE二级','计算机等级二级','全国计算机二级','计算机二级证书'],'boost':6},
    'A050': {'keywords':['计算机一级','NCRE一级','计算机等级一级','全国计算机一级'],'boost':5},
    'A051': {'keywords':['普通话二甲','普通话一级','普通话水平二甲','普通话一乙','普通话等级一级'],'boost':8},
    'A052': {'keywords':['普通话二乙','普通话水平二乙','普通话等级二乙'],'boost':6},
    'A053': {'keywords':['普通话三甲','普通话水平三甲'],'boost':4},
    'A057': {'keywords':['均分85','平均分85','成绩优秀','绩点','GPA','平均成绩','学业成绩'],'boost':6},

    # ── 文体: 体育 ──
    'S001': {'keywords':['院运动会','院运会参赛','院田径运动会'],'boost':5},
    'S004': {'keywords':['院运动会前三','院运会冠军','院运会亚军','院运会季军','院运会第一名','院运会第二名','院运会第三名'],'boost':7},
    'S005': {'keywords':['院运动会破记录','院记录','院运会记录'],'boost':9},
    'S007': {'keywords':['校运动会','校运会参赛','校田径运动会'],'boost':6},
    'S009': {'keywords':['校运动会前三','校运会冠军','校运会亚军','校运会季军','校运会第一名'],'boost':8},
    'S011': {'keywords':['校运动会破记录','校记录','校运会记录'],'boost':10},
    'S013': {'keywords':['省高校运动会','省大运会','省运会','省级运动会'],'boost':10},
    'S016': {'keywords':['全国运动会','全国大运会','全运会','国家级运动会'],'boost':10},

    # ── 文体: 文艺 ──
    'S019': {'keywords':['院级文艺演出','院文艺','院级节目','院文艺表演'],'boost':6},
    'S023': {'keywords':['校级文艺演出','校文艺','校级节目','校庆演出','校文艺表演'],'boost':8},
    'S028': {'keywords':['省级文艺演出','省文艺','省级节目','省文艺表演'],'boost':9},
    'S033': {'keywords':['社团竞赛','社团比赛','社团活动竞赛'],'boost':5},
    'S037': {'keywords':['演讲比赛国家级','全国辩论','全国征文','国家级演讲比赛'],'boost':10},
    'S041': {'keywords':['演讲比赛省级','省辩论','省级征文','省级演讲比赛'],'boost':9},
    'S045': {'keywords':['演讲比赛校级','校辩论','校级征文','校级演讲比赛'],'boost':7},
}

CATEGORY_SIGNALS = {
    'moral': ['干部','志愿','献血','宿舍','文明','荣誉称号','优秀学生','优秀团员','优秀团干','军训','值班','代表大会','班集体','学生会','团总支','主席团','部长','干事','三下乡','见义勇为','义务劳动','班委','班干部','辅导员助理','助班','舍长','宿舍长','社长','会长','红十字会','青协','社联','辩论队','国旗护卫队','学生处','助理班主任','预干','勤工助学','广播站','艺术团','编辑部','广师视频','科技站','党支部','助学贷款','医保','党务','就业','心理','校园电视台'],
    'academic': ['论文','SCI','EI','核心期刊','竞赛','互联网+','挑战杯','电子设计','大创','创新项目','立项','专利','软件著作权','著作权','英语四级','英语六级','CET','计算机等级','普通话','双学位','辅修','考研','研究生','成绩','均分','学术','发表','期刊','证书','四级','六级','NCRE','软著','攀登计划','大创项目','科研','发明','授权','申请','GPA','绩点','考试','合格','425','成绩单','全国计算机','创新训练'],
    'sports': ['运动会','体育','田径','篮球','足球','游泳','文艺','演出','表演','歌手','合唱','舞蹈','器乐','辩论','演讲','征文','跳绳','拔河','马拉松','武术','乒乓球','羽毛球','网球','比赛','名次','冠军','亚军','季军','奖牌','记录','破记录','文艺演出','节目','社团竞赛','体育比赛','文艺比赛','运动会比赛'],
}

LEVEL_SIGNALS = {
    '国家级': ['国家级','国家','全国','部级','教育部','国赛','国家教育部'],
    '省级': ['省级','省赛','省部级','省教育厅','全省'],
    '校级': ['校级','校赛','校庆','校内','学校','全校'],
    '院级': ['院级','院赛','院内','学院','本院'],
    '班级': ['班级','班内','班会','本班'],
}

# ══════════════════════════════════════════
# Detection Functions
# ══════════════════════════════════════════
def detect_level(text: str) -> Optional[str]:
    """检测级别，国家级优先"""
    provincial_patterns = [
        r'(?:广东|北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门)赛区',
        r'省赛',
        r'省级',
        r'赛区.{0,12}(?:一等奖|二等奖|三等奖|特等奖|最高奖)',
    ]
    if any(re.search(p, text) for p in provincial_patterns):
        return '省级'
    for level, signals in LEVEL_SIGNALS.items():
        for s in signals:
            if s in text:
                return level
    return None

def detect_category(text: str) -> Optional[str]:
    """检测大类"""
    scores = {}
    for cat, signals in CATEGORY_SIGNALS.items():
        score = sum(1 for s in signals if s in text)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else None


def _detect_ncre_item_id(text: str) -> Optional[str]:
    """计算机等级考试只保留材料明确写出的等级。"""
    if not any(s in text for s in ['全国计算机等级考试', '计算机等级考试', 'NCRE']):
        return None
    level_map = {
        '四': 'A047', '4': 'A047', 'level4': 'A047',
        '三': 'A048', '3': 'A048', 'level3': 'A048',
        '二': 'A049', '2': 'A049', 'level2': 'A049',
        '一': 'A050', '1': 'A050', 'level1': 'A050',
    }
    compact = text.lower().replace(' ', '')
    for marker, item_id in level_map.items():
        if marker.startswith('level'):
            if marker in compact:
                return item_id
            continue
        patterns = [
            f'全国计算机等级考试{marker}级',
            f'计算机等级考试{marker}级',
            f'{marker}级合格证书',
            f'ncre{marker}级',
        ]
        if any(p.lower().replace(' ', '') in compact for p in patterns):
            return item_id
    return None


GENERIC_TITLE_TOKENS = {
    '一等奖', '二等奖', '三等奖', '特等奖', '最高奖', '获奖', '参加',
    '合格', '通过', '委员', '成员', '高级', '中级', '初级',
    '国家级', '省级', '校级', '院级', '班级',
    '正职', '副职', '核心', '负责', '负责人',
}


def _meaningful_title_words(title: str) -> list:
    words = re.findall(r'[一-鿿\w]+', title)
    useful = []
    for w in words:
        if len(w) < 2:
            continue
        if w.isdigit():
            continue
        if w in GENERIC_TITLE_TOKENS:
            continue
        if re.fullmatch(r'\d+分?', w):
            continue
        useful.append(w)
    return useful

# ══════════════════════════════════════════
# Core Matching Algorithm
# ══════════════════════════════════════════
def match_catalog_items(text: str, catalog_items: list, filename: str = '',
                        extra_keyword: str = '') -> list:
    """对提取的文字内容进行综测项目匹配"""
    # 预处理搜索文本
    clean_text = _normalize_text(f"{filename} {extra_keyword} {text}")
    detected_level = detect_level(clean_text)
    detected_category = detect_category(clean_text)
    explicit_ncre_item_id = _detect_ncre_item_id(clean_text)

    scores = []
    for item in catalog_items:
        if explicit_ncre_item_id and item['id'] in {'A047', 'A048', 'A049', 'A050'} and item['id'] != explicit_ncre_item_id:
            continue

        item_score = 0.0
        reasons = []
        has_primary_match = False

        # 1. 签名关键词匹配（模糊匹配）
        sig = ITEM_SIGNATURES.get(item['id'], {}) or ITEM_SIGNATURES.get(str(item['id'])[:4], {})
        sig_keywords = sig.get('keywords', [])
        sig_boost = sig.get('boost', 5)
        matched_sigs = _contains_any_fuzzy(clean_text, sig_keywords, threshold=0.7)
        if matched_sigs:
            item_score += len(matched_sigs) * sig_boost
            has_primary_match = True
            reasons.append(f"命中关键词: {', '.join(matched_sigs[:3])}")

        # 2. 标题关键词匹配（精确+模糊）
        short_words = _meaningful_title_words(item['title'])
        title_matched = _contains_any_fuzzy(clean_text, short_words, threshold=0.8)
        if title_matched:
            item_score += len(title_matched) * 8
            has_primary_match = True
            if not reasons:
                reasons.append(f"标题匹配: {', '.join(title_matched[:3])}")

        # 3. 描述关键词匹配
        desc_words = re.findall(r'[一-鿿]+', item.get('description', ''))
        desc_matched = [w for w in desc_words if len(w) >= 2 and w in clean_text]
        if desc_matched:
            item_score += min(len(desc_matched) * 3, 15)
            has_primary_match = True

        # 4. 级别吻合奖励
        if detected_level and detected_level == item.get('level', ''):
            item_score += 8
            if has_primary_match:
                reasons.append(f"级别吻合({detected_level})")

        # 5. 类别吻合奖励
        if detected_category and detected_category == item.get('category', ''):
            item_score += 6

        # 6. section匹配奖励
        section = item.get('section', '')
        if section and section in clean_text:
            item_score += 4
            has_primary_match = True

        # 7. note/备注匹配
        note = item.get('note', '')
        if note:
            note_words = re.findall(r'[一-鿿]+', note)
            note_matched = [w for w in note_words if len(w) >= 2 and w in clean_text]
            if note_matched:
                item_score += len(note_matched) * 2
                has_primary_match = True

        if item_score > 0 and has_primary_match:
            scores.append({
                'id': item['id'], 'title': item['title'],
                'description': item.get('description', ''),
                'category': item['category'],
                'category_name': item.get('category_name', ''),
                'level': item.get('level', ''), 'score_val': item.get('score', 0),
                'icon': item.get('icon', 'fa-star'),
                'section': item.get('section', ''), 'note': item.get('note', ''),
                'raw_score': item_score, 'reasons': reasons,
            })

    scores.sort(key=lambda x: x['raw_score'], reverse=True)

    # 归一化置信度（改进算法）
    if scores:
        top_score = scores[0]['raw_score']
        for s in scores:
            # 用对数尺度平滑分数
            ratio = s['raw_score'] / max(top_score, 1)
            confidence = int(30 + ratio * 65)
            # 如果远高于第二，提权
            if len(scores) > 1 and s['raw_score'] > scores[1]['raw_score'] * 1.5:
                confidence = min(95, confidence + 10)
            # 如果有多个原因，提权
            if len(s.get('reasons', [])) >= 2:
                confidence = min(95, confidence + 5)
            s['confidence'] = min(95, confidence)
            s['decision'] = 'high' if s['confidence'] >= 80 else ('medium' if s['confidence'] >= 40 else 'low')
            s['reason'] = _generate_reason(s)

    return scores[:8]  # 返回更多结果

def _generate_reason(match: dict) -> str:
    reasons = match.get('reasons', [])
    reasons_text = '；'.join(reasons) if reasons else '综合文本特征匹配'
    conf = match['confidence']
    verdict = '高度匹配，建议自动通过' if conf >= 80 else ('中度匹配，建议人工审核' if conf >= 40 else '低度匹配，证据不足')
    return f"[置信度{conf}%] {reasons_text}。{verdict}。"

# ══════════════════════════════════════════
# Main Analysis
# ══════════════════════════════════════════

def _is_image_type(file_type: str) -> bool:
    """判断是否为图片类型"""
    ft = file_type.lower()
    return ft in ('image', 'jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp')


def _build_catalog_json(catalog_items: list, max_items: int = 250) -> str:
    """构建综测目录JSON摘要"""
    items = []
    for i in catalog_items[:max_items]:
        items.append({
            'id': i['id'], 'title': i['title'],
            'category': i.get('category_name', i.get('category', '')),
            'level': i.get('level', ''), 'score': i.get('score', 0),
            'section': i.get('section', ''), 'description': i.get('description', '')[:80],
        })
    return json.dumps(items, ensure_ascii=False, indent=2)


def _build_catalog_index(catalog_items: list) -> dict:
    """构建目录索引 {id: item}"""
    return {i['id']: i for i in catalog_items}


def _score_confidence(match: dict, extracted_text: str, filename: str = '',
                     student_name: str = '', student_id: str = '') -> dict:
    """多维度置信度评估：综合材料权威性、成果完成度、完整性等因素调整置信度"""
    base_conf = match.get('confidence', 50)
    reasons = []
    adjustments = []
    text = extracted_text or filename

    # ════════════════════════════════════════
    # 因素1: 材料证明力 — 是否为官方证明文件
    # ════════════════════════════════════════
    authority_signals = ['证书', '证明', '聘书', '成绩单', '考试', '合格证', '等级证书',
                         '毕业证', '学位证', '资格证书', '执业证书', '结业证书', '获奖证书',
                         '荣誉证书', '表彰', '通知书', '录用通知', '授权书', '登记证']
    authority_count = sum(1 for s in authority_signals if s in text)
    if authority_count >= 2:
        adjustments.append(('材料权威性高', 10))
        reasons.append(f'含{authority_count}个官方文件信号')
    elif authority_count == 1:
        adjustments.append(('材料具权威性', 5))
    elif authority_count == 0:
        adjustments.append(('缺乏官方文件特征', -8))
        reasons.append('未检测到"证书/证明/成绩单"等官方文件标识')

    # ════════════════════════════════════════
    # 因素2: 成果完成度 — 是否已取得成果(而非过程文件)
    # ════════════════════════════════════════
    completion_signals = ['一等奖', '二等奖', '三等奖', '特等奖', '金奖', '银奖', '铜奖',
                          '冠军', '亚军', '季军', '合格', '通过', '授权', '授予', '颁发',
                          '获评', '评为', '被评为', '荣获', '授予', '得分', '成绩',
                          '取到', '获得', '获取', '颁发日期', '发证日期', '授予日期',
                          '优秀', '先进', '标兵', '先进个人']
    completion_count = sum(1 for s in completion_signals if s in text)
    if completion_count >= 3:
        adjustments.append(('成果完成度高', 12))
        reasons.append(f'含{completion_count}个成果完成信号')
    elif completion_count >= 1:
        adjustments.append(('成果已完成', 6))
    else:
        adjustments.append(('未检测到成果完成信号', -5))

    # ════════════════════════════════════════
    # 因素3: 负面信号 — 未完成/申请中/备考中 = 重大扣分
    # ════════════════════════════════════════
    negative_signals = {
        '报名': -25, '申请中': -30, '备考': -25, '准备': -15,
        '未通过': -35, '不合格': -35, '不及格': -35, '未参加': -30,
        '弃考': -40, '缺考': -40, '挂科': -35, '补考': -25,
        '落选': -30, '淘汰': -30, '暂未': -20, '待定': -15,
        '等待': -10, '拟申报': -20, '草稿': -25, '样本': -30,
        '模板': -30, '样例': -20,
    }
    neg_penalty = 0
    neg_hits = []
    for signal, penalty in negative_signals.items():
        if signal in text:
            neg_penalty += penalty
            neg_hits.append(signal)
    if neg_hits:
        adjustments.append(('检测到负面信号', neg_penalty))
        reasons.append(f'材料含: {", ".join(neg_hits[:3])}')

    # ════════════════════════════════════════
    # 因素4: OCR / 文字提取质量
    # ════════════════════════════════════════
    text_len = len(text.replace('\n', '').replace(' ', ''))
    filename_has_signal = False
    if filename:
        fname_lower_for_quality = filename.lower()
        filename_has_signal = any(s in fname_lower_for_quality for s in [
            '证书', '证明', '成绩', '聘书', '奖', '表彰', 'cert',
            'exam', 'score', 'transcript', 'hcia', 'hcip', 'hcie', 'huawei', '华为'
        ])
    if text_len < 10:
        if filename_has_signal:
            adjustments.append(('OCR为空但文件名可用', -8))
            reasons.append('OCR未提取到有效文字，已使用文件名/关键词辅助匹配')
        else:
            adjustments.append(('文字提取极差', -35))
            reasons.append('OCR几乎无有效文字，可能为空白/模糊图片')
    elif text_len < 30:
        adjustments.append(('文字提取较差', -15))
        reasons.append(f'仅提取{text_len}字，信息量不足')
    elif text_len < 60:
        adjustments.append(('文字量偏低', -5))
    elif text_len >= 200:
        adjustments.append(('文字信息充足', 5))

    # ════════════════════════════════════════
    # 因素5: 学生身份匹配
    # ════════════════════════════════════════
    identity_matched = False
    if student_name and len(student_name) >= 2 and student_name in text:
        identity_matched = True
        adjustments.append(('学生姓名匹配', 5))
        reasons.append(f'材料含学生姓名"{student_name}"')
    if student_id and len(student_id) >= 6 and student_id in text:
        adjustments.append(('学号匹配', 5) if not identity_matched else ('', 3))
        if not identity_matched:
            reasons.append(f'材料含学号')
    if student_name and not identity_matched and student_id and student_id not in text:
        adjustments.append(('未检测到学生身份信息', -3))

    # ════════════════════════════════════════
    # 因素6: 颁发机构/公章
    # ════════════════════════════════════════
    org_signals = ['教育部', '省教育厅', '考试院', '人力资源', '社会保障',
                   '中国计算机', '全国计算机', '大学英语', '全国大学生',
                   '共青团', '教育部考试中心', '工业和信息化部', '国家知识产权局',
                   '知识产权局', '专利局', '版权局', '学校', '学院', '大学',
                   '委员会', '协会', '学会', '组委会', '竞赛组委会']
    org_count = sum(1 for s in org_signals if s in text)
    if org_count >= 2:
        adjustments.append(('有颁发机构信息', 6))
        reasons.append(f'检测到{org_count}个机构/公章信号')
    elif org_count == 1:
        adjustments.append(('含机构信息', 3))

    # ════════════════════════════════════════
    # 因素7: 文件名信号
    # ════════════════════════════════════════
    if filename:
        fname_lower = filename.lower()
        bad_fname_signals = ['img_', 'dsc_', 'screenshot', '截图', 'photo', '照片',
                             '微信图片', 'mmexport', 'image', '未命名', 'untitled']
        good_fname_signals = ['证书', '证明', '成绩', '聘书', '奖', '表彰', 'cert',
                              'exam', 'score', 'transcript']
        is_bad_name = any(s in fname_lower for s in bad_fname_signals)
        is_good_name = any(s in fname_lower for s in good_fname_signals)
        if is_bad_name and not is_good_name:
            adjustments.append(('文件名无意义', -3))
        elif is_good_name:
            adjustments.append(('文件名含信号', 3))

    # ════════════════════════════════════════
    # 因素8: 材料级别与项目级别一致性
    # ════════════════════════════════════════
    item_level = match.get('level', '')
    text_level = detect_level(text)
    if item_level and text_level and item_level == text_level:
        adjustments.append(('级别吻合', 4))
    elif item_level and text_level and item_level != text_level:
        # 已在 _validate_matches 中处理，这里微调
        pass

    # ════════════════ 汇总 ════════════════
    total_adjustment = sum(adj for _, adj in adjustments if adj != 0)
    new_conf = base_conf + total_adjustment
    cap, cap_reasons = _strict_confidence_cap(match, extracted_text, filename, student_name, student_id)
    if cap_reasons:
        reasons.extend(cap_reasons)
        adjustments.append(('?????', cap - 98))
    new_conf = max(5, min(98, new_conf, cap))

    # 负向信号极多时直接标记为高风险
    risk_level = 'low'
    if neg_penalty <= -30:
        risk_level = 'high'
    elif neg_penalty <= -15 or text_len < 20:
        risk_level = 'medium'

    match['confidence'] = new_conf
    match['decision'] = 'high' if new_conf >= 80 else ('medium' if new_conf >= 40 else 'low')
    match['risk_level'] = risk_level

    # 构建详细理由
    detail_parts = [f'原始置信度{base_conf}%']
    if reasons:
        detail_parts.append('; '.join(reasons))
    if total_adjustment != 0:
        detail_parts.append(f'综合调整{total_adjustment:+d}%')
    match['confidence_detail'] = '。'.join(detail_parts)
    match['reason'] = (match.get('reason', '') + ' | ' + match['confidence_detail'])

    return match


def _validate_matches(matches: list, extracted_text: str) -> list:
    """后置校验：检查 LLM 匹配结果是否与材料文字存在明显矛盾"""
    validated = []
    for m in matches:
        item_id = m.get('id', '')
        title = m.get('title', '')
        item_level = m.get('level', '')
        conf = m.get('confidence', 50)
        reason = m.get('reason', '')
        warnings = []

        # 校验1：数字级别矛盾检测
        number_map = {'一': ['一', '1', '壹'], '二': ['二', '2', '贰', '两'],
                      '三': ['三', '3', '叁'], '四': ['四', '4', '肆']}
        for num_label, num_chars in number_map.items():
            # 标题含某数字，但文字中明确只有另一个数字
            if num_label in title:
                other_nums = [n for k, n in number_map.items() if k != num_label]
                for other_list in other_nums:
                    for other_char in other_list:
                        if f'{other_char}级' in extracted_text and f'{num_label}级' not in extracted_text:
                            warnings.append(f'材料写"{other_char}级"但匹配了"{num_label}级"')
                            conf = max(10, conf - 25)
                        # 更严格的检查：对证书类
                        for prefix in ['计算机', '英语', 'CET', '普通话']:
                            if prefix in title and prefix in extracted_text:
                                if f'{prefix}{other_char}级' in extracted_text and f'{prefix}{num_label}级' not in extracted_text:
                                    warnings.append(f'{prefix}级别矛盾')
                                    conf = max(10, conf - 30)

        # 校验2：组织层级矛盾（校 vs 院）
        if '校' in title and item_level == '校级':
            if '院学生会' in extracted_text and '校学生会' not in extracted_text:
                warnings.append('材料为院级但匹配了校级项目')
                conf = max(10, conf - 20)
        if '院' in title and item_level == '院级':
            if '校学生会' in extracted_text and '院学生会' not in extracted_text:
                warnings.append('材料为校级但匹配了院级项目')
                conf = max(10, conf - 20)

        # 校验3：职务等级矛盾（正 vs 副，主席 vs 部长 vs 干事）
        rank_hierarchy = {
            '主席': ['副主席', '部长', '副部长', '干事', '预干'],
            '部长': ['副部长', '干事', '预干'],
            '干事': ['预干'],
        }
        for higher, lowers in rank_hierarchy.items():
            if higher in title:
                for lower in lowers:
                    # 如果文字只提到低级职务，不应匹配高级
                    if lower in extracted_text and higher not in extracted_text:
                        # 检查是否确实只提到低级的
                        title_no_higher = higher not in extracted_text
                        if title_no_higher:
                            warnings.append(f'材料为"{lower}"但匹配了"{higher}"')
                            conf = max(10, conf - 20)
                            break
                if warnings:
                    break

        # 校验4：获奖等级矛盾
        award_checks = [
            (['一等奖', '特等奖', '金奖', '第一名'], ['二等奖', '三等奖', '银奖', '铜奖', '第二名', '第三名']),
            (['冠军'], ['亚军', '季军']),
        ]
        for high_awards, low_awards in award_checks:
            title_has_high = any(a in title for a in high_awards)
            title_has_low = any(a in title for a in low_awards)
            text_has_high = any(a in extracted_text for a in high_awards)
            text_has_low = any(a in extracted_text for a in low_awards)
            if title_has_high and text_has_low and not text_has_high:
                warnings.append('获奖等级矛盾：材料为低等奖但匹配了高等奖')
                conf = max(10, conf - 20)
            if title_has_low and text_has_high and not text_has_low:
                warnings.append('获奖等级矛盾：材料为高等奖但匹配了低等奖')
                conf = max(10, conf - 15)

        # 应用警告
        if warnings:
            reason = reason + ' [校验警告: ' + '; '.join(warnings) + ']'
        m['confidence'] = min(98, max(5, conf))
        m['reason'] = reason
        validated.append(m)

    validated.sort(key=lambda x: x['confidence'], reverse=True)
    return validated


def _first_match(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        found = re.search(pattern, text, re.IGNORECASE)
        if found:
            return next((part for part in found.groups() if part), found.group(0)).strip()
    return ''




def _strict_contains_any(text: str, words: list[str]) -> bool:
    return any(word and word in text for word in words)


def _extract_award_granularity(text: str) -> dict:
    """Extract project level and prize level separately so project+award is preserved."""
    source = _normalize_text(text or '')
    project_level = ''
    contextual_levels = [
        ('\u7701\u7ea7', [r'\u7701\u7ea7.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)', r'\u7701\u8d5b.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)', r'\u8d5b\u533a.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)']),
        ('\u56fd\u5bb6\u7ea7', [r'\u56fd\u5bb6\u7ea7.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)', r'\u56fd\u8d5b.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)']),
        ('\u6821\u7ea7', [r'\u6821\u7ea7.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)']),
        ('\u9662\u7ea7', [r'\u9662\u7ea7.{0,8}(?:\u7279\u7b49\u5956|\u4e00\u7b49\u5956|\u4e8c\u7b49\u5956|\u4e09\u7b49\u5956)']),
    ]
    for label, patterns in contextual_levels:
        if any(re.search(pattern, source) for pattern in patterns):
            project_level = label
            break
    level_patterns = [
        ('\u56fd\u9645\u7ea7', ['\u56fd\u9645\u7ea7', '\u56fd\u9645', '\u5168\u7403']),
        ('\u56fd\u5bb6\u7ea7', ['\u56fd\u5bb6\u7ea7', '\u5168\u56fd', '\u56fd\u8d5b', '\u6559\u80b2\u90e8', '\u56fd\u5bb6']),
        ('\u7701\u7ea7', ['\u7701\u7ea7', '\u7701\u8d5b', '\u8d5b\u533a', '\u5e7f\u4e1c\u7701', '\u5168\u7701', '\u7701\u90e8\u7ea7']),
        ('\u6821\u7ea7', ['\u6821\u7ea7', '\u6821\u8d5b', '\u5168\u6821', '\u5b66\u6821']),
        ('\u9662\u7ea7', ['\u9662\u7ea7', '\u9662\u8d5b', '\u5b66\u9662', '\u672c\u9662']),
        ('\u73ed\u7ea7', ['\u73ed\u7ea7', '\u73ed\u5185']),
    ]
    if not project_level:
        for label, patterns in level_patterns:
            if any(pattern in source for pattern in patterns):
                project_level = label
                break
    prize_level = ''
    prize_patterns = [
        ('\u7279\u7b49\u5956', ['\u7279\u7b49\u5956', '\u6700\u9ad8\u5956']),
        ('\u4e00\u7b49\u5956', ['\u4e00\u7b49\u5956', '\u7b2c\u4e00\u540d', '\u51a0\u519b', '\u91d1\u5956']),
        ('\u4e8c\u7b49\u5956', ['\u4e8c\u7b49\u5956', '\u7b2c\u4e8c\u540d', '\u4e9a\u519b', '\u94f6\u5956']),
        ('\u4e09\u7b49\u5956', ['\u4e09\u7b49\u5956', '\u7b2c\u4e09\u540d', '\u5b63\u519b', '\u94dc\u5956']),
        ('\u4f18\u79c0\u5956', ['\u4f18\u79c0\u5956']),
    ]
    for label, patterns in prize_patterns:
        if any(pattern in source for pattern in patterns):
            prize_level = label
            break
    return {
        'project_level': project_level,
        'prize_level': prize_level,
        'award_level_detail': ''.join([project_level, prize_level]) or project_level or prize_level,
    }


def _strict_confidence_cap(match: dict, text: str, filename: str,
                           student_name: str = '', student_id: str = '') -> tuple[int, list[str]]:
    """Evidence-calibrated upper bound. Prevents raw matching from becoming 98% without a complete evidence chain."""
    source = f'{filename}\n{text or ""}\n{match.get("title", "")}\n{match.get("reason", "")}'
    normalized = _normalize_text(source)
    cap = 96
    reasons = []

    official = _strict_contains_any(normalized, [
        '\u8bc1\u4e66', '\u8bc1\u660e', '\u5408\u683c\u8bc1', '\u83b7\u5956\u8bc1\u4e66', '\u6210\u7ee9\u5355',
        '\u8003\u8bd5\u9662', '\u6559\u80b2\u90e8', '\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u90e8', '\u5de5\u4fe1\u90e8',
        '\u7ec4\u59d4\u4f1a', '\u59d4\u5458\u4f1a', '\u534f\u4f1a', '\u5b66\u6821', '\u5b66\u9662', '\u5927\u5b66',
        '\u516c\u7ae0', '\u76d6\u7ae0', 'seal', 'certificate'
    ])
    completion = _strict_contains_any(normalized, [
        '\u4e00\u7b49\u5956', '\u4e8c\u7b49\u5956', '\u4e09\u7b49\u5956', '\u7279\u7b49\u5956', '\u4f18\u79c0\u5956',
        '\u91d1\u5956', '\u94f6\u5956', '\u94dc\u5956', '\u5408\u683c', '\u901a\u8fc7', '\u8363\u83b7', '\u83b7\u5956',
        '\u6388\u4e88', '\u9881\u53d1', '\u6210\u7ee9'
    ])
    date_ok = bool(re.search(r'20\d{2}\s*(?:\u5e74|[-./]\s*)\s*(?:0?[1-9]|1[0-2])', normalized, re.I))
    text_len = len(re.sub(r'\s+', '', normalized))
    award = _extract_award_granularity(normalized)
    title = _normalize_text(match.get('title', ''))
    requires_prize = any(word in title for word in ['\u7ade\u8d5b', '\u6311\u6218\u676f', '\u4e92\u8054\u7f51+', '\u84dd\u6865\u676f', '\u7535\u5b50\u8bbe\u8ba1', '\u83b7\u5956', '\u5956'])

    if not official:
        cap = min(cap, 78)
        reasons.append('\u7f3a\u5c11\u5b98\u65b9\u8bc1\u4e66/\u673a\u6784/\u516c\u7ae0\u4fe1\u53f7')
    if not completion:
        cap = min(cap, 74)
        reasons.append('\u672a\u8bc6\u522b\u5230\u83b7\u5956\u6216\u5b8c\u6210\u4fe1\u53f7')
    if not date_ok:
        cap = min(cap, 88)
        reasons.append('\u7f3a\u5c11\u53ef\u6838\u9a8c\u65e5\u671f')
    if text_len < 40:
        cap = min(cap, 72)
        reasons.append('OCR\u6709\u6548\u6587\u672c\u4e0d\u8db3')
    elif text_len < 100:
        cap = min(cap, 86)
        reasons.append('OCR\u6587\u672c\u4fe1\u606f\u504f\u5c11')

    if student_name:
        has_name = student_name in normalized
        has_id = bool(student_id and student_id in normalized)
        extracted = _extract_audit_features(text, filename, student_name, student_id).get('detected_name', '')
        if extracted and not (student_name in extracted or extracted in student_name or SequenceMatcher(None, student_name.lower(), extracted.lower()).ratio() >= 0.72):
            cap = min(cap, 72)
            reasons.append('\u6750\u6599\u59d3\u540d\u4e0e\u5f53\u524d\u8d26\u53f7\u4e0d\u4e00\u81f4')
        elif not has_name and not has_id:
            cap = min(cap, 82)
            reasons.append('\u7f3a\u5c11\u5f53\u524d\u5b66\u751f\u8eab\u4efd\u5339\u914d\u8bc1\u636e')

    if match.get('level') and award['project_level'] and award['project_level'] != match.get('level'):
        cap = min(cap, 68)
        reasons.append(f'\u6750\u6599\u8d5b\u4e8b\u7ea7\u522b\u4e3a{award["project_level"]}\uff0c\u4e0e\u5339\u914d\u9879\u76ee{match.get("level")}\u4e0d\u4e00\u81f4')
    if requires_prize and not award['prize_level']:
        cap = min(cap, 80)
        reasons.append('\u672a\u8bc6\u522b\u5230\u660e\u786e\u5956\u9879\u7b49\u7ea7')
    if requires_prize and award['prize_level'] and not award['project_level']:
        cap = min(cap, 82)
        reasons.append(f'\u4ec5\u8bc6\u522b\u5230{award["prize_level"]}\uff0c\u7f3a\u5c11\u56fd\u5bb6/\u7701/\u6821/\u9662\u7ea7\u522b')

    return cap, reasons

def _extract_audit_features(text: str, filename: str, student_name: str = '', student_id: str = '') -> dict:
    source = f'{filename}\n{text}'
    detected_name = _first_match([
        r'姓名\s*([\u4e00-\u9fa5]{2,4})(?=\d|身份证|证件|Name|参加|$)',
        r'姓名[:：\s]*([\u4e00-\u9fa5]{2,4})',
        r'姓\s*名\s*([\u4e00-\u9fa5]{2,4})(?=\d|身份证|证件|Name|参加|$)',
        r'Name[:：\s]*([A-Za-z\s]{2,40})',
        r'(Yulin\s+Xiao|Xiao\s+Yulin)',
        r'([\u4e00-\u9fa5]{2,4})同学',
    ], source)
    if not detected_name and student_name and student_name in source:
        detected_name = student_name
    event_name = _first_match([
        r'((?:第.{1,12}届)?[^，。\n]{2,40}(?:竞赛|挑战赛|大赛|杯|证书|认证|活动))',
        r'([A-Za-z0-9\s-]{3,60}(?:Competition|Challenge|Certificate|Certification|Contest))',
    ], source)
    award_level = _first_match([
        r'(国家级|省级|校级|院级|班级|国际级)',
        r'(特等奖|一等奖|二等奖|三等奖|优秀奖|金奖|银奖|铜奖)',
        r'(provincial|national|campus|college|first prize|second prize|third prize)',
    ], source)
    rank = _first_match([
        r'(负责人|队长|成员|普通成员|指导老师|联合创始人|Co-Founder|co founder|participant|winner)',
        r'(第[一二三四五六七八九十0-9]+名|Top\s*\d+)',
    ], source)
    date_value = _first_match([
        r'((?:202\d)[-./年](?:0?[1-9]|1[0-2])[-./月](?:0?[1-9]|[12]\d|3[01])日?)',
        r'((?:202\d)(?:\s*年\s*|\s*[-./]\s*|\s+)(?:0?[1-9]|1[0-2])\s*月?)',
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})',
    ], source)
    is_name_matched = bool(
        student_name and detected_name and (
            student_name in detected_name or detected_name in student_name
            or SequenceMatcher(None, student_name.lower(), detected_name.lower()).ratio() >= 0.72
        )
    )
    award_granularity = _extract_award_granularity(source)
    if award_granularity.get('award_level_detail'):
        award_level = award_granularity['award_level_detail']
    return {
        'detected_name': detected_name,
        'student_name': student_name,
        'student_id': student_id,
        'is_name_matched': is_name_matched,
        'event_name': event_name,
        'award_level': award_level,
        'project_level': award_granularity.get('project_level', ''),
        'prize_level': award_granularity.get('prize_level', ''),
        'award_level_detail': award_granularity.get('award_level_detail', ''),
        'rank_type': rank,
        'date': date_value,
        'has_official_seal': any(word in source for word in ['公章', '盖章', 'seal', 'Seal', '委员会', '组委会', '证书']),
        'is_tampered': any(word in source for word in ['涂改', '篡改', 'P图', '伪造']),
    }


def _audit_status(confidence: float, risk_tags: list[str], missing_fields: list[dict]) -> str:
    if confidence < 60 or 'TAMPER_SUSPECTED' in risk_tags:
        return 'HIGH_RISK'
    if missing_fields or risk_tags:
        return 'NEED_SUPPLEMENT'
    if confidence >= 95:
        return 'HIGH_CONFIDENCE'
    return 'PENDING_HUMAN'


def _build_audit_payload(match: dict, extracted_text: str, filename: str,
                         student_name: str = '', student_id: str = '') -> dict:
    confidence = float(match.get('confidence') or 0)
    features = _extract_audit_features(extracted_text, filename, student_name, student_id)
    text_blob = f'{filename}\n{extracted_text}\n{match.get("title", "")}\n{match.get("reason", "")}'
    lower_blob = text_blob.lower()
    risk_tags = []
    missing_fields = []

    if features['is_tampered']:
        risk_tags.append('TAMPER_SUSPECTED')
    if student_name and features['detected_name'] and not features['is_name_matched']:
        risk_tags.append('NAME_MISMATCH')
    if any(word in lower_blob for word in ['929', 'challenge startup', 'co-founder', 'co founder', '中葡']):
        risk_tags.extend(['COMPLEX_TEAM_ROLE', 'UNLISTED_COMPETITION'])
        missing_fields.append({
            'field_key': 'team_rank_proof',
            'field_name': '团队成员排名及加分比例证明',
            'guidance_tips': '请上传包含指导老师签字或学院盖章的团队成员排序表，以判定按负责人100%还是成员比例折算加分。',
        })
        missing_fields.append({
            'field_key': 'official_notice_screenshot',
            'field_name': '学校或学院发布的官方通知截图',
            'guidance_tips': '冷门或境外赛事需补充校院通知、转发通知或学院认可证明。',
        })
    if not features['detected_name'] and student_name:
        risk_tags.append('IDENTITY_UNCLEAR')
        missing_fields.append({
            'field_key': 'identity_match_proof',
            'field_name': '个人身份匹配证明',
            'guidance_tips': '请补充能同时显示姓名、学号或账号归属的材料。',
        })
    if not features.get('date'):
        risk_tags.append('DATE_UNCLEAR')
        missing_fields.append({
            'field_key': 'date_proof',
            'field_name': '??/??????',
            'guidance_tips': '?????????????????????????',
        })
    if ('??' in match.get('title', '') or '?' in match.get('title', '')) and not features.get('award_level_detail'):
        risk_tags.append('AWARD_LEVEL_UNCLEAR')
        missing_fields.append({
            'field_key': 'award_level_proof',
            'field_name': '???????????',
            'guidance_tips': '??????????/?/?/???????/???/???????',
        })
    if confidence < 60:
        risk_tags.append('LOW_CONFIDENCE')
    elif confidence < 90 and not risk_tags:
        risk_tags.append('HUMAN_CONFIRM_REQUIRED')

    # De-duplicate while preserving order.
    risk_tags = list(dict.fromkeys(risk_tags))
    deduped_missing = []
    seen_fields = set()
    for item in missing_fields:
        if item['field_key'] not in seen_fields:
            deduped_missing.append(item)
            seen_fields.add(item['field_key'])

    clause_text = match.get('section') or match.get('note') or match.get('description') or match.get('title') or ''
    audit_chain = [
        f"Step 1: OCR/文档解析提取材料文本，来源文件为「{filename}」。",
        f"Step 2: 匹配综测目录项目「{match.get('title', '')}」，置信度 {confidence:.1f}%。",
        f"Step 3: 对照细则条目「{clause_text or '待管理员确认'}」，建议分值 {match.get('score_val', match.get('score', 0))} 分。",
    ]
    if risk_tags:
        audit_chain.append(f"Step 4: 触发风控标签 {', '.join(risk_tags)}，需管理员复核或要求补件。")

    return {
        'status': _audit_status(confidence, risk_tags, deduped_missing),
        'confidence_score': confidence,
        'matched_regulation': {
            'section': match.get('section', ''),
            'clause_id': match.get('id', ''),
            'clause_text': clause_text,
            'score_calculated': match.get('score_val', match.get('score', 0)),
        },
        'extracted_features': features,
        'risk_assessment': {
            'risk_tags': risk_tags,
            'risk_description': '；'.join(item['guidance_tips'] for item in deduped_missing) or match.get('reason', ''),
        },
        'missing_fields': deduped_missing,
        'audit_chain': audit_chain,
    }


def _llm_match_with_tools(extracted_text: str, catalog_items: list,
                          filename: str, extra_keyword: str) -> Optional[list]:
    """使用自定义 LLM + 工具调用进行综测项目匹配"""
    if not _get_llm() or not extracted_text.strip():
        return None

    from custom_llm import chat, MATCH_TOOL, parse_tool_matches, parse_json_matches

    catalog_json = _build_catalog_json(catalog_items, 250)
    catalog_by_id = _build_catalog_index(catalog_items)

    system_prompt = f"""你是高校综测加分审核助手。你同时承担 OCR 文本抽取校对、风控合规官和综测细则映射器三种职责。你的任务是根据证明材料文字内容，从目录中精准匹配综测加分项目。

你必须使用 match_comprehensive_item 工具提交匹配结果。只对你**确信匹配**的项目调用工具。

═══════════════════════════════════════
【必须遵守的匹配规则 — 违反将导致审核事故】
═══════════════════════════════════════

▎规则1：数字级别必须精确
- 材料写"二级"→只能匹配"二级"项目，绝不可匹配"一级/三级/四级"
- 材料写"CET-4/四级"→只能匹配四级，绝不能匹配六级(CET-6)
- 材料写"二甲"→只能匹配二甲，不能匹配二乙或三甲
- 材料写"一等奖/第一名"→不能匹配"二等奖/三等奖"

▎规则2：组织层级(校/院)必须吻合
- 材料写"院学生会"→匹配院级项目(M019-M022)，不能匹配校级(M001-M005)
- 材料写"校学生会"→匹配校级项目(M001-M005)，不能匹配院级(M019-M022)
- 同理适用于：青协、社联、红十字会、艺术团等组织

▎规则3：职务等级(正/副/干事)必须对应
- 材料写"主席团/主席"→不能匹配"部长/干事"
- 材料写"副部长"→不能匹配"部长(正)"或"主席"
- 材料写"预干"→不能匹配"正式干事"或"部长"

▎规则4：获奖等级与实际奖项一致
- 名次必须对应：第一名→不匹配"第二三名"
- 院级获奖→不匹配"校级获奖"项目

▎规则5：动态匹配数量 — 精确则少，模糊则广
- 目录有精确对应（名称+级别完全吻合）→ 只提交这1-2个精确项目
- 目录无精确对应（如特殊比赛名、冷门证书等）→ 广泛提交4-8个可能相关的候选
- 模糊场景下置信度30-50也提交，标记为"供人工参考"

▎规则6：风控与置信度
- 90-100：官方正式证书、姓名与学生一致、细则有明确对应条款。
- 60-89：证书真实但属于复合/冷门场景，需要结合团队排名、校院通知或官方来源确认。
- 30-59：材料模糊、关键印章/姓名/来源缺失，必须提示补充材料。
- 0-29：涉嫌伪造、姓名不符或完全不属于综测加分范畴。
- 对英文证书、境外赛事、创业挑战赛、Co-Founder/团队身份等场景，必须降低置信度并提示补充团队分工或校院认可证明。

═══════════════════════════════════════
以下是电信学院完整综测项目目录（共{len(catalog_items)}项）：
{catalog_json}"""

    user_message = f"""请按以下步骤分析证明材料：

【第1步】先列出材料中明确提到的所有关键信息：
- 活动/证书/荣誉/职务的**具体全称**
- 明确的**级别**（国家/省/校/院/班级）
- 明确的**数字等级**（一/二/三/四，甲/乙等）
- 明确的**角色**（参赛者/获奖者/干部/志愿者/组织者）
- 明确的**组织名称**（校学生会/院学生会/青协等）

【第2步】对每条信息，根据是否存在精确匹配来动态决定提交数量：
- 目录中有精确对应（名称+级别一致）→ 只提交这1-2个，不画蛇添足
- 目录中无精确对应 → 广泛提交4-8个可能相关的候选（同类/同级/同分段的项目），置信度30-50也提交供人工参考

文件名: {filename}
学生补充关键词: {extra_keyword or '无'}

===== 材料文字内容 =====
{extracted_text[:4000]}
===== 内容结束 =====

现在开始第1步：先列出材料中的关键信息。然后进行第2步匹配。"""

    try:
        resp = chat(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message},
            ],
            tools=[MATCH_TOOL],
            temperature=0.1,
        )

        matches = parse_tool_matches(resp, catalog_by_id)

        if not matches and resp.content:
            matches = parse_json_matches(resp.content, catalog_by_id)

        if matches:
            matches = _validate_matches(matches, extracted_text)
            return matches[:8]
        return None
    except Exception:
        try:
            resp = chat(
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message + '\n\n请返回JSON数组: [{"id":"项目ID","confidence":0-100,"reason":"理由"}]'},
                ],
                temperature=0.1,
            )
            matches = parse_json_matches(resp.content, catalog_by_id)
            if matches:
                matches = _validate_matches(matches, extracted_text)
                return matches[:8]
        except Exception:
            pass
        return None


def analyze_files(uploaded_files: list, catalog_items: list,
                  extra_keyword: str = '', use_llm: bool = True,
                  student_name: str = '', student_id: str = '') -> list:
    """智能分析入口 — 自定义LLM(工具调用)优先，关键词规则降级
    student_name/student_id 用于多维度置信度评估中的身份验证"""
    results = []
    llm_ok = _get_llm()

    for uf in uploaded_files:
        fp = uf.get('file_path', '')
        ftype = uf.get('file_type', '')
        fname = uf.get('original_filename', '')

        # Step 1: 提取文字（图片走OCR，PDF/DOCX走文档解析）
        extracted = ''
        if fp and os.path.exists(fp):
            extracted = extract_text_from_file(fp, ftype)
        else:
            extracted = fname

        matches = []
        ai_enhanced = False

        # Step 2: LLM 工具调用匹配（可用时优先）
        if llm_ok and extracted.strip():
            lm = _llm_match_with_tools(extracted, catalog_items, fname, extra_keyword)
            if lm:
                matches = lm
                ai_enhanced = True

        # Step 3: 降级 — 关键词规则匹配
        if not matches:
            matches = match_catalog_items(
                text=extracted, catalog_items=catalog_items,
                filename=fname, extra_keyword=extra_keyword,
            )

        # Step 4: 多维度置信度评估
        confidence_text = extracted if extracted.strip() else f"{fname} {extra_keyword}".strip()
        for m in matches:
            m = _score_confidence(m, confidence_text, fname, student_name, student_id)
            if not m.get('category_name'):
                m['category_name'] = {
                    'moral': '品德行为表现',
                    'academic': '学业表现',
                    'sports': '文体表现'
                }.get(m.get('category', ''), '')
            m['audit'] = _build_audit_payload(m, extracted, fname, student_name, student_id)

        results.append({
            'file_id': uf.get('id'), 'filename': fname,
            'extracted_text': extracted[:500], 'extracted_text_full': extracted,
            'has_text_content': bool(extracted.strip()),
            'matches': matches, 'ai_enhanced': ai_enhanced,
        })
    return results

# ══════════════════════════════════════════
# Admin AI Fill
# ══════════════════════════════════════════
def ai_suggest_item_fields(activity_name: str, activity_description: str = '') -> dict:
    suggestion = {
        'category': detect_category(activity_name + activity_description) or 'academic',
        'level': detect_level(activity_name + activity_description) or '校级',
        'score_range': '3-10', 'section': '', 'subcategory': '',
        'reason': '基于关键词规则推断',
    }
    if _get_llm():
        try:
            from custom_llm import chat
            resp = chat(
                messages=[{'role':'user','content':f"""综测项目录入助手。推荐分类。
活动: {activity_name}
描述: {activity_description or '无'}
大类: moral/academic/sports 级别: 国家级/省级/校级/院级/班级
返回JSON: {{"category":"","level":"","suggested_score":0,"section":"","reason":""}}"""}],
                temperature=0.1)
            content = resp.content
            if content:
                jm = re.search(r'\{[\s\S]*\}', content)
                if jm:
                    suggestion.update(json.loads(jm.group(0)))
                    suggestion['ai_enhanced'] = True
        except: pass
    return suggestion

# ══════════════════════════════════════════
# Regulation Extraction
# ══════════════════════════════════════════
def extract_regulation_items(text: str) -> list:
    """从综测细则文本提取加分项目"""
    items = []
    patterns = [
        (r'([^，。,\.\n]{4,40})[，,]\s*(?:每[^\d]*)?(?:加|计|得|获|奖)\s*(\d+(?:\.\d+)?)\s*分', 'moral'),
        (r'([^，。,\.\n]{4,40})[：:，,]\s*(国家级|省级|校级|院级)[^，,]{0,10}[，,]?\s*(?:加|计|得)?\s*(\d+(?:\.\d+)?)\s*分', 'academic'),
        (r'([^，。,\.\n]{4,40})[，,]?\s*(?:每[^\d]*)?(?:加|计|得)\s*(\d+(?:\.\d+)?)\s*分', 'academic'),
        (r'参加\s*([^，。,\.\n]{2,30})[，,]\s*(?:每[^\d]*)?(?:加|计|得)\s*(\d+(?:\.\d+)?)\s*分', 'moral'),
    ]
    for pat, default_cat in patterns:
        for m in re.finditer(pat, text):
            groups = m.groups()
            if len(groups) == 2:
                title, score = groups
                level = detect_level(title) or '校级'
                cat = detect_category(title) or default_cat
            else:
                title, level, score = groups
                cat = 'academic'
            title = title.strip()
            if len(title) < 2 or any(it['title'] == title for it in items):
                continue
            items.append({
                'title': title, 'category': cat, 'level': level,
                'score': float(score), 'section': '',
                'description': f'源自细则: {m.group(0)[:80]}',
                'confidence': min(90, 40 + len(title) * 2),
                'source_text': m.group(0),
            })
    items.sort(key=lambda x: x['confidence'], reverse=True)
    return items[:50]

def extract_regulation_items_llm(text: str) -> list:
    if not _get_llm(): return []
    try:
        from custom_llm import chat
        resp = chat(
            messages=[{'role':'user','content':f"""高校综测细则解析。提取所有加分项目返回JSON:
[{{"title":"项目名","category":"moral/academic/sports","level":"国家级/省级/校级/院级/班级","score":0,"section":"分类","description":""}}]
细则文本: {text[:4000]}"""}],
            temperature=0.1)
        content = resp.content
        if content:
            jm = re.search(r'\[[\s\S]*\]', content)
            if jm:
                items = json.loads(jm.group(0))
                for it in items:
                    it['confidence'] = 85
                    it['source_text'] = it.get('description', '')
                return items[:50]
    except: pass
    return []

# ══════════════════════════════════════════
# 成绩单 OCR 课程识别
# ══════════════════════════════════════════

# 课程类型关键词映射
COURSE_TYPE_KEYWORDS = {
    '必修': ['必修', '必修课', '专业必修', '公共必修', '学科必修'],
    '限选': ['限选', '限选课', '专业限选', '方向限选', '选修(限)', '限定选修'],
    '任选': ['任选', '任选课', '专业任选', '自由选修', '选修(任)', '任意选修'],
    '公选': ['公选', '公选课', '公共选修', '通识选修', '通识课', '校选', '校选修'],
}

# 常见课程名模式（用于区分课程名和无关文字）
COURSE_NAME_PATTERNS = [
    # 中文字符+可能的括号内容
    re.compile(r'^[一-鿿（）()\d\w\s\-+]+$'),
    # 包含"学"、"概论"、"原理"、"设计"等课程特征词
    re.compile(r'[一-鿿]+(?:学|概论|原理|设计|实验|实习|实训|课程|英语|数学|物理|化学|计算机|编程|工程)'),
]


def _detect_course_type(text: str) -> str:
    """从文本中检测课程类型，默认'必修'"""
    text_lower = text.lower()
    for ctype, keywords in COURSE_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower or kw in text:
                return ctype
    return '必修'


def _looks_like_course_name(text: str) -> bool:
    """判断文本是否像课程名"""
    text = text.strip()
    if len(text) < 2 or len(text) > 40:
        return False
    # 纯数字或纯标点不是课程名
    if re.match(r'^[\d\s\.\,\;\:\!\?\-—\+]+$', text):
        return False
    # 至少包含一个中文字符
    if not re.search(r'[一-鿿]', text):
        return False
    # 不能是常见无关词
    skip_words = {'成绩单', '学号', '姓名', '班级', '专业', '学院', '学年', '学期',
                  '序号', '备注', '合计', '平均', '总分', '制表', '审核', '第', '页',
                  '课程名称', '成绩', '学分', '绩点', '课程类型', '考试', '考查',
                  '必修课', '选修课', '限选课', '公选课', '教务处', '打印', '日期'}
    if text.strip() in skip_words:
        return False
    return True


def _extract_number_fields(tokens: list) -> tuple:
    """从 token 列表中提取成绩(0-100)和学分(0.5-15)"""
    numbers = []
    for t in tokens:
        try:
            val = float(t.replace(',', '.').strip())
            if val > 0:
                numbers.append(val)
        except (ValueError, AttributeError):
            continue

    grade = None
    credits = None

    for n in numbers:
        if n <= 15 and n >= 0.5:
            # 可能是学分
            if credits is None:
                credits = n
        elif 0 < n <= 100:
            # 可能是成绩
            if grade is None:
                grade = n
        elif 15 < n <= 100:
            # 只能是成绩
            if grade is None:
                grade = n

    # 如果成绩>100不合理，可能顺序反了
    if grade is not None and grade > 100:
        grade = None
    if credits is not None and credits > 15:
        credits = None

    return grade, credits


def extract_courses_from_ocr_text(ocr_text: str) -> list:
    """
    从成绩单 OCR 文字中提取课程列表。
    支持格式：
    - 表格类：课程名 \t 成绩 \t 学分 \t 课程类型
    - 行式类：课程名 成绩 学分
    - 每行一门课

    返回: [{"course_name": str, "grade": float, "credits": float,
            "course_type": str, "confidence": float}]
    """
    if not ocr_text or not ocr_text.strip():
        return []

    lines = ocr_text.strip().split('\n')
    results = []
    seen_names = set()

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # 先检测课程类型关键词
        line_course_type = _detect_course_type(line)

        # 策略1：制表符分隔
        if '\t' in line:
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            if 2 <= len(parts) <= 6:
                name_candidates = [p for p in parts if _looks_like_course_name(p)]
                if name_candidates:
                    course_name = name_candidates[0]
                    remaining = [p for p in parts if p != course_name]
                    grade, credits = _extract_number_fields(remaining)
                    if grade is not None and credits is not None:
                        conf = 0.85 if len(parts) >= 3 else 0.7
                        if course_name not in seen_names:
                            seen_names.add(course_name)
                            results.append({
                                'course_name': course_name,
                                'grade': grade,
                                'credits': credits,
                                'course_type': line_course_type,
                                'confidence': conf,
                            })
                        continue

        # 策略2：空格/逗号分隔
        # 尝试用连续空格分割
        if '  ' in line:
            parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip() and len(p.strip()) > 1]
        else:
            parts = [p.strip() for p in re.split(r'[\s,，、]+', line) if p.strip()]

        # 过滤出可能的字段
        name_candidates = [p for p in parts if _looks_like_course_name(p)]
        if not name_candidates:
            continue

        course_name = name_candidates[0]
        remaining = [p for p in parts if p != course_name]
        grade, credits = _extract_number_fields(remaining)

        if grade is not None and credits is not None:
            conf = 0.75
            if course_name not in seen_names:
                seen_names.add(course_name)
                results.append({
                    'course_name': course_name,
                    'grade': grade,
                    'credits': credits,
                    'course_type': line_course_type,
                    'confidence': conf,
                })

    # 策略3：如果上面都没有识别到，用整行正则匹配
    if not results:
        # 匹配模式：中文课程名 + 数字(成绩) + 数字(学分)
        row_pattern = re.compile(
            r'([一-鿿（）()\w]{2,20}?)\s*[：:\s]*\s*(\d{1,3}(?:\.\d)?)\s*[分]?\s*[，,\s]+\s*(\d{1,2}(?:\.\d)?)\s*学?分?',
            re.MULTILINE
        )
        for m in row_pattern.finditer(ocr_text):
            course_name = m.group(1).strip()
            try:
                grade = float(m.group(2))
                credits = float(m.group(3))
            except ValueError:
                continue
            if not _looks_like_course_name(course_name):
                continue
            if grade > 100 or credits > 15:
                continue
            if course_name not in seen_names:
                seen_names.add(course_name)
                results.append({
                    'course_name': course_name,
                    'grade': grade,
                    'credits': credits,
                    'course_type': _detect_course_type(course_name),
                    'confidence': 0.65,
                })

    return results


def compute_file_hash(file_path: str) -> str:
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha.update(chunk)
    return sha.hexdigest()
