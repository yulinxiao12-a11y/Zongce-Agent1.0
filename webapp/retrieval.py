# -*- coding: utf-8 -*-
"""
检索增强引擎 — BM25 + TF-IDF 混合检索
依据《综测材料AI审核机制设计》"层级化分片 + 多路混合检索"设计

替代原有的纯关键词规则匹配，提供:
1. BM25 概率检索 — 精确关键词匹配
2. TF-IDF 稠密向量 — 语义相似度
3. 层级化分片 — 按"大类-子类-级别"三级索引
4. 混合评分融合 — BM25×α + TF-IDF×(1-α)
"""
import re
import math
from collections import defaultdict
from typing import Optional


# ══════════════════════════════════════════
# 1. 文本预处理
# ══════════════════════════════════════════

# 中文分词 — 使用 jieba 如果可用，否则退化为字符级 bigram
try:
    import jieba
    _jieba_available = True
except ImportError:
    _jieba_available = False


def tokenize(text: str) -> list[str]:
    """将文本切分为 token 列表"""
    if not text:
        return []
    if _jieba_available:
        tokens = jieba.lcut(text)
    else:
        # Fallback: 字符级 bigram + 单字
        text = re.sub(r'[^一-鿿A-Za-z0-9]', ' ', str(text))
        chars = text.replace(' ', '')
        tokens = []
        for i in range(len(chars)):
            tokens.append(chars[i])
            if i < len(chars) - 1:
                tokens.append(chars[i:i+2])
        # 也保留英文数字token
        for word in re.findall(r'[A-Za-z0-9]+', text):
            if len(word) >= 2:
                tokens.append(word.lower())
    # 过滤纯标点/空白
    return [t for t in tokens if t.strip() and len(t.strip()) >= 1]


def normalize_text(text: str) -> str:
    """文本标准化"""
    text = re.sub(r'\s+', ' ', text or '')
    text = re.sub(r'[（(]', '(', text)
    text = re.sub(r'[）)]', ')', text)
    return text.strip().lower()


# ══════════════════════════════════════════
# 2. BM25 实现
# ══════════════════════════════════════════

class BM25:
    """BM25 概率检索模型

    BM25(D, Q) = Σ IDF(qi) × (f(qi,D) × (k1+1)) / (f(qi,D) + k1×(1-b+b×|D|/avgdl))

    参数:
        k1: 词频饱和度 (默认 1.5)
        b: 文档长度归一化 (默认 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[dict] = []       # [{'id':..., 'tokens':[...], 'metadata':{...}}]
        self.doc_freqs: dict[str, int] = defaultdict(int)  # 词 → 出现该词的文档数
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0
        self.N: int = 0
        self._indexed = False

    def index(self, documents: list[dict]):
        """构建 BM25 索引

        Args:
            documents: [{'id': str, 'text': str, 'metadata': dict}]
        """
        self.documents = []
        self.doc_freqs.clear()
        self.doc_lengths = []
        seen_tokens_per_doc = []

        for doc in documents:
            tokens = tokenize(normalize_text(doc.get('text', '')))
            self.documents.append({
                'id': doc.get('id', ''),
                'tokens': tokens,
                'metadata': doc.get('metadata', {}),
            })
            self.doc_lengths.append(len(tokens))
            unique_tokens = set(tokens)
            seen_tokens_per_doc.append(unique_tokens)
            for t in unique_tokens:
                self.doc_freqs[t] += 1

        self.N = len(self.documents)
        self.avgdl = sum(self.doc_lengths) / max(self.N, 1)
        self._indexed = True

    def _idf(self, term: str) -> float:
        """逆文档频率"""
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score(self, query: str, doc_idx: int) -> float:
        """计算单个文档的 BM25 分数"""
        if not self._indexed or doc_idx >= self.N:
            return 0.0

        query_tokens = tokenize(normalize_text(query))
        doc = self.documents[doc_idx]
        doc_tokens = doc['tokens']
        dl = self.doc_lengths[doc_idx]
        if dl == 0:
            return 0.0

        score = 0.0
        tf_map = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        for qt in query_tokens:
            if qt not in tf_map:
                continue
            idf = self._idf(qt)
            tf = tf_map[qt]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += idf * numerator / denominator

        return score

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 检索，返回 top_k 结果"""
        if not self._indexed:
            return []

        results = []
        for i in range(self.N):
            s = self.score(query, i)
            if s > 0:
                results.append({
                    'index': i,
                    'id': self.documents[i]['id'],
                    'bm25_score': round(s, 3),
                    'metadata': self.documents[i]['metadata'],
                })

        results.sort(key=lambda x: x['bm25_score'], reverse=True)
        return results[:top_k]


# ══════════════════════════════════════════
# 3. TF-IDF 向量检索
# ══════════════════════════════════════════

class TFIDFRetriever:
    """TF-IDF 稠密向量检索器

    使用余弦相似度计算查询与文档的语义关联度
    """

    def __init__(self):
        self.documents: list[dict] = []
        self.vocabulary: dict[str, int] = {}     # term → index
        self.doc_vectors: list[dict[int, float]] = []  # [{term_idx: tfidf_weight}]
        self.idf_values: dict[int, float] = {}
        self._indexed = False

    def index(self, documents: list[dict]):
        """构建 TF-IDF 索引"""
        self.documents = []
        self.vocabulary = {}
        doc_term_freqs = []
        N = len(documents)

        # First pass: collect vocabulary
        for doc in documents:
            tokens = tokenize(normalize_text(doc.get('text', '')))
            self.documents.append({
                'id': doc.get('id', ''),
                'tokens': tokens,
                'metadata': doc.get('metadata', {}),
            })
            tf = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            doc_term_freqs.append(tf)
            for t in tf:
                if t not in self.vocabulary:
                    self.vocabulary[t] = len(self.vocabulary)

        # Second pass: compute TF-IDF vectors
        doc_freq = defaultdict(int)
        for tf in doc_term_freqs:
            for t in tf:
                doc_freq[t] += 1

        # IDF
        for term, idx in self.vocabulary.items():
            self.idf_values[idx] = math.log((N + 1) / (doc_freq.get(term, 1) + 1)) + 1

        # Document vectors (sparse)
        for tf in doc_term_freqs:
            vec = {}
            norm_sq = 0.0
            for term, freq in tf.items():
                idx = self.vocabulary[term]
                tfidf = (1 + math.log(freq)) * self.idf_values.get(idx, 0)
                vec[idx] = tfidf
                norm_sq += tfidf ** 2
            # L2 normalize
            norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
            vec = {k: v / norm for k, v in vec.items()}
            self.doc_vectors.append(vec)

        self._indexed = True

    def _query_vector(self, query: str) -> dict[int, float]:
        """将查询转为 TF-IDF 向量"""
        tokens = tokenize(normalize_text(query))
        tf = defaultdict(int)
        for t in tokens:
            tf[t] += 1

        vec = {}
        norm_sq = 0.0
        for term, freq in tf.items():
            idx = self.vocabulary.get(term)
            if idx is None:
                continue
            tfidf = (1 + math.log(freq)) * self.idf_values.get(idx, 0)
            vec[idx] = tfidf
            norm_sq += tfidf ** 2

        norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
        return {k: v / norm for k, v in vec.items()}

    def _cosine_similarity(self, vec1: dict[int, float], vec2: dict[int, float]) -> float:
        """稀疏向量余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        # 两个向量都已 L2 归一化，余弦相似度 = 点积
        dot = 0.0
        for idx, v1 in vec1.items():
            v2 = vec2.get(idx, 0)
            dot += v1 * v2
        return max(0.0, min(1.0, dot))

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """TF-IDF 语义检索"""
        if not self._indexed:
            return []

        qvec = self._query_vector(query)
        if not qvec:
            return []

        results = []
        for i, dvec in enumerate(self.doc_vectors):
            sim = self._cosine_similarity(qvec, dvec)
            if sim > 0.01:  # 过滤极低相似度
                results.append({
                    'index': i,
                    'id': self.documents[i]['id'],
                    'tfidf_score': round(sim, 3),
                    'metadata': self.documents[i]['metadata'],
                })

        results.sort(key=lambda x: x['tfidf_score'], reverse=True)
        return results[:top_k]


# ══════════════════════════════════════════
# 4. 混合检索引擎
# ══════════════════════════════════════════

class HybridRetriever:
    """BM25 + TF-IDF 混合检索引擎

    融合策略:
    - α: BM25 权重 (默认 0.5)，精确匹配与语义理解的平衡
    - 层级分片加成: 同类、同级、同分段的项目额外加分
    """

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.bm25 = BM25()
        self.tfidf = TFIDFRetriever()
        self.catalog_items: list[dict] = []
        self._indexed = False

    def index(self, catalog_items: list[dict]):
        """构建索引

        Args:
            catalog_items: [{
                'id': str, 'title': str, 'description': str,
                'category': str, 'level': str, 'score': float,
                'section': str, 'subcategory': str, ...
            }]
        """
        self.catalog_items = catalog_items

        # 构建检索文档: 标题 + 描述 + 分类名 + 级别 + section
        documents = []
        for item in catalog_items:
            text_parts = [
                item.get('title', ''),
                item.get('description', ''),
                item.get('section', ''),
                item.get('category', ''),
                item.get('level', ''),
                item.get('subcategory', ''),
            ]
            doc_text = ' '.join(str(p) for p in text_parts if p)
            documents.append({
                'id': item['id'],
                'text': doc_text,
                'metadata': {
                    'category': item.get('category', ''),
                    'level': item.get('level', ''),
                    'section': item.get('section', ''),
                    'subcategory': item.get('subcategory', ''),
                    'score': item.get('score', 0),
                    'title': item.get('title', ''),
                },
            })

        self.bm25.index(documents)
        self.tfidf.index(documents)
        self._indexed = True

    def search(self, query: str, top_k: int = 15,
               detected_level: str = '', detected_category: str = '') -> list[dict]:
        """混合检索

        Args:
            query: 搜索文本 (OCR提取+文件名+extra_keyword)
            top_k: 返回数量
            detected_level: 从文本中检测到的级别 (用于层级加成)
            detected_category: 从文本中检测到的大类 (用于层级加成)

        Returns:
            [{
                'id': str, 'title': str, 'score': float (hybrid),
                'bm25_score': float, 'tfidf_score': float,
                'level_bonus': float, 'category_bonus': float,
                ...original catalog fields
            }]
        """
        if not self._indexed:
            return []

        bm25_results = {r['id']: r for r in self.bm25.search(query, top_k * 2)}
        tfidf_results = {r['id']: r for r in self.tfidf.search(query, top_k * 2)}

        # 合并结果
        all_ids = set(bm25_results.keys()) | set(tfidf_results.keys())
        merged = []

        for item_id in all_ids:
            bm = bm25_results.get(item_id, {})
            tf = tfidf_results.get(item_id, {})
            bm_score = bm.get('bm25_score', 0)
            tf_score = tf.get('tfidf_score', 0)

            # 归一化
            # BM25 分数范围不定，需要归一化到 [0,1]
            # TF-IDF 已经在 [0,1]
            # 使用 sigmoid 对 BM25 进行压缩
            bm_norm = 2 / (1 + math.exp(-bm_score)) - 1  # sigmoid 变换到 [0,1]

            hybrid = self.alpha * bm_norm + (1 - self.alpha) * tf_score

            # ── 层级化分片加成 ──
            metadata = bm.get('metadata', {}) or tf.get('metadata', {})
            level_bonus = 0.0
            category_bonus = 0.0

            if detected_level and metadata.get('level') == detected_level:
                level_bonus = 0.08  # 级别吻合 +8% 加成
            if detected_category and metadata.get('category') == detected_category:
                category_bonus = 0.06  # 类别吻合 +6% 加成

            final_score = hybrid + level_bonus + category_bonus

            merged.append({
                'id': item_id,
                'title': metadata.get('title', ''),
                'hybrid_score': round(final_score, 4),
                'bm25_score': round(bm_score, 3),
                'tfidf_score': round(tf_score, 3),
                'bm25_norm': round(bm_norm, 3),
                'level_bonus': level_bonus,
                'category_bonus': category_bonus,
                'category': metadata.get('category', ''),
                'level': metadata.get('level', ''),
                'section': metadata.get('section', ''),
                'subcategory': metadata.get('subcategory', ''),
                'score_val': metadata.get('score', 0),
            })

        merged.sort(key=lambda x: x['hybrid_score'], reverse=True)
        return merged[:top_k]

    def batch_search(self, queries: list[str], top_k: int = 10) -> list[list[dict]]:
        """批量检索 (多个查询并行)"""
        return [self.search(q, top_k) for q in queries]


# ══════════════════════════════════════════
# 5. 便捷工厂函数
# ══════════════════════════════════════════

_global_retriever: Optional[HybridRetriever] = None


def get_retriever(catalog_items: list[dict] = None, force_rebuild: bool = False) -> HybridRetriever:
    """获取全局检索引擎实例（单例模式）"""
    global _global_retriever
    if _global_retriever is None or force_rebuild:
        if catalog_items:
            _global_retriever = HybridRetriever(alpha=0.5)
            _global_retriever.index(catalog_items)
    return _global_retriever


def semantic_match(query: str, catalog_items: list[dict], top_k: int = 15) -> list[dict]:
    """便捷函数：语义匹配查询到综测目录

    Args:
        query: OCR提取的文本
        catalog_items: 综测目录列表
        top_k: 返回数量

    Returns:
        排序后的匹配结果
    """
    retriever = HybridRetriever(alpha=0.5)
    retriever.index(catalog_items)
    return retriever.search(query, top_k)
