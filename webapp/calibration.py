# -*- coding: utf-8 -*-
"""
置信度标定引擎 — Temperature Scaling + Isotonic Regression (PAVA)
依据《综测材料AI审核机制设计》八维评估体系设计

目标: 使"置信度90%"的材料实际正确概率确实≈90%
"""
import math
import json
import os
from typing import Optional


# ══════════════════════════════════════════
# 1. Temperature Scaling
# ══════════════════════════════════════════
# 原始公式: P_cal = softmax(logits / T)
# 当我们没有原始 logits 时，使用概率空间变换近似:
#   calibrated = sigmoid( logit(raw/100) / T ) × 100
# 其中 logit(p) = ln(p/(1-p))
#
# T > 1: 降低过度自信（平滑）
# T < 1: 提高置信度锐度
# T = 1: 不变


def _logit(p: float) -> float:
    """logit 变换: ln(p/(1-p))，将概率映射到实数空间"""
    p = max(0.001, min(0.999, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    """sigmoid: 1/(1+e^-x)"""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < -700 else 1.0


def temperature_scale(confidence: float, T: float = 1.5) -> float:
    """应用温度缩放到置信度分数

    Args:
        confidence: 原始置信度 (0-100)
        T: 温度参数，默认 1.5（适度平滑过度自信）

    Returns:
        校准后的置信度 (0-100)
    """
    if T <= 0 or T == 1.0:
        return confidence
    prob = confidence / 100.0
    calibrated_prob = _sigmoid(_logit(prob) / T)
    return round(calibrated_prob * 100, 1)


# ══════════════════════════════════════════
# 2. Isotonic Regression — PAVA 算法
# ══════════════════════════════════════════
# PAVA (Pool Adjacent Violators Algorithm)
# 将原始分单调映射为校准分，确保单调性约束


def pava_fit(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """PAVA 拟合: 合并违反单调性的相邻区间

    Args:
        pairs: [(raw_score, calibrated_target), ...] 按 raw_score 升序排列

    Returns:
        [(raw_low, raw_high, calibrated_value), ...]
        即 isotonic regression 的分段常数函数
    """
    if not pairs:
        return []

    # 确保按 raw_score 升序
    pairs = sorted(pairs, key=lambda x: x[0])
    n = len(pairs)

    # 每个点初始化为自己的区间
    # blocks[i] = (sum_raw, sum_target, count)
    blocks = [(x, y, 1) for x, y in pairs]

    # PAVA: 从前往后扫描，合并违反单调性的相邻块
    i = 0
    while i < len(blocks) - 1:
        curr_val = blocks[i][1] / blocks[i][2]  # 当前块平均
        next_val = blocks[i + 1][1] / blocks[i + 1][2]  # 下一块平均

        if curr_val > next_val:
            # 违反单调递增约束 → 合并
            merged = (
                blocks[i][0] + blocks[i + 1][0],
                blocks[i][1] + blocks[i + 1][1],
                blocks[i][2] + blocks[i + 1][2],
            )
            blocks[i] = merged
            del blocks[i + 1]
            # 回退检查新合并块是否违反与前一块的约束
            if i > 0:
                i -= 1
        else:
            i += 1

    # 构建分段常数函数
    result = []
    cum_count = 0
    for raw_sum, target_sum, count in blocks:
        cum_count += count
        result.append((cum_count, target_sum / count))

    return result


def pava_predict(raw_score: float, isotonic_model: list, raw_range: tuple = (0, 100)) -> float:
    """使用 PAVA 模型预测校准后的置信度

    Args:
        raw_score: 原始置信度
        isotonic_model: pava_fit 的输出
        raw_range: 原始分范围

    Returns:
        校准后的置信度
    """
    if not isotonic_model:
        return raw_score

    lo, hi = raw_range
    score = max(lo, min(hi, raw_score))

    # 找到所在区间
    prev_val = isotonic_model[0][1] if isotonic_model else raw_score
    next_val = isotonic_model[-1][1] if isotonic_model else raw_score

    for i, (boundary, val) in enumerate(isotonic_model):
        if i == 0 and score <= lo + (hi - lo) * boundary / len(isotonic_model):
            return round(val * 100, 1)
        if i > 0:
            prev_boundary = isotonic_model[i - 1][0]
            prev_val = isotonic_model[i - 1][1]
            if ((score - lo) / (hi - lo)) * len(isotonic_model) <= boundary:
                # 线性插值
                frac = (score - lo) / (hi - lo)
                prev_frac = prev_boundary / len(isotonic_model)
                curr_frac = boundary / len(isotonic_model)
                if curr_frac > prev_frac:
                    alpha = (frac - prev_frac) / (curr_frac - prev_frac)
                    calibrated = prev_val + alpha * (val - prev_val)
                else:
                    calibrated = val
                return round(calibrated * 100, 1)

    return raw_score


# ══════════════════════════════════════════
# 3. 完整校准流水线
# ══════════════════════════════════════════

# 默认校准参数 — 基于文档四大场景经验值
# 这些参数可以在收集足够管理端反馈后通过真实数据重新拟合
DEFAULT_TEMPERATURE = 1.2

# 默认校准曲线 — 极端值保持原样，中段适度降噪
# 数据点: (raw_confidence, calibrated_target)
# 基于文档四大场景 + 工业界校准最佳实践
DEFAULT_ISOTONIC_POINTS = [
    (5,  0.08),   # 极低 → 保持低分
    (15, 0.15),   # 低 (场景二)
    (30, 0.28),   # 低-中
    (50, 0.48),   # 中
    (65, 0.63),   # 中-高
    (75, 0.74),   # 高
    (85, 0.85),   # 高 (场景一区域)
    (91, 0.91),   # 高 (场景一/三)
    (95, 0.95),   # 极高 (直通阈值)
    (98, 0.98),   # 极高
]


def calibrate_confidence(raw_confidence: float,
                         temperature: float = DEFAULT_TEMPERATURE,
                         use_isotonic: bool = True) -> dict:
    """完整的置信度校准流水线

    默认策略: 仅使用 Isotonic Regression 校准（非参数化单调映射）。
    Temperature Scaling 适用于有原始 logits 的神经网络场景，
    本系统为多维度组合评分，Isotonic 更合适。
    """
    raw = max(5, min(98, raw_confidence))

    # Isotonic Regression — 直接使用校准点插值
    iso_score = _interpolate_calibration(raw, DEFAULT_ISOTONIC_POINTS)

    # Temperature Scaling 作为可选的平滑手段
    ts_score = temperature_scale(raw, temperature) if temperature != 1.0 else raw

    final = iso_score

    steps = (
        f'原始{raw:.1f}% → PAVA校准{iso_score:.1f}%'
    )

    return {
        'raw': raw,
        'temperature_scaled': ts_score,
        'isotonic_calibrated': iso_score,
        'final': final,
        'steps': steps,
        'temperature': temperature,
    }


def _interpolate_calibration(raw: float, points: list[tuple[float, float]]) -> float:
    """在校准点之间进行线性插值

    points: [(raw_percentile, calibrated_probability), ...] 按 percentile 升序
    """
    if not points:
        return raw

    points = sorted(points, key=lambda x: x[0])
    raw = max(0, min(100, raw))

    # 低于第一个点
    if raw <= points[0][0]:
        return round(points[0][1] * 100, 1)

    # 高于最后一个点
    if raw >= points[-1][0]:
        return round(points[-1][1] * 100, 1)

    # 在两点之间线性插值
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if raw <= x1:
            alpha = (raw - x0) / (x1 - x0) if x1 > x0 else 0
            calibrated = y0 + alpha * (y1 - y0)
            return round(calibrated * 100, 1)

    return raw


def _pava_predict_percentile(raw: float, model: list) -> float:
    """基于分位数的 PAVA 预测 — 简化但鲁棒的实现"""
    # model from pava_fit: [(cum_count, avg_value), ...]
    # 转换为 (percentile, prob) 格式
    if not model or len(model) < 1:
        return raw

    total = model[-1][0] if model else 1
    points = [(boundary / total * 100, val) for boundary, val in model]
    return _interpolate_calibration(raw, points)


# ══════════════════════════════════════════
# 4. 历史数据驱动的参数更新
# ══════════════════════════════════════════

def update_calibration_from_feedback(feedback_records: list[dict]) -> dict:
    """从管理端反馈数据中更新校准参数

    Args:
        feedback_records: [{
            'raw_confidence': float,
            'ai_decision': str,
            'admin_decision': 'approved' | 'rejected',
            'is_correct': bool,  # 管理员是否认可AI判断
        }]

    Returns:
        更新后的校准参数和建议
    """
    if len(feedback_records) < 10:
        return {'updated': False, 'reason': '反馈数据不足(需≥10条)', 'temperature': DEFAULT_TEMPERATURE}

    # 计算每个置信度区间的实际正确率
    bins = {}
    for rec in feedback_records:
        raw = rec.get('raw_confidence', 50)
        bin_key = (raw // 10) * 10  # 0, 10, 20, ... 90
        if bin_key not in bins:
            bins[bin_key] = {'correct': 0, 'total': 0}
        bins[bin_key]['total'] += 1
        if rec.get('is_correct', rec.get('admin_decision') == 'approved'):
            bins[bin_key]['correct'] += 1

    # 构建经验校准点
    new_points = []
    for bin_key in sorted(bins.keys()):
        bin_data = bins[bin_key]
        accuracy = bin_data['correct'] / max(bin_data['total'], 1)
        new_points.append((bin_key + 5, accuracy))  # 区间中点

    # 用 PAVA 平滑
    if len(new_points) >= 3:
        smoothed = pava_fit(new_points)
        # 提取平滑后的点
        calibrated_points = []
        for boundary, val in smoothed:
            percentile = (boundary / len(new_points)) * 100
            calibrated_points.append((round(percentile, 0), round(val, 3)))

        return {
            'updated': True,
            'new_points': calibrated_points,
            'temperature': DEFAULT_TEMPERATURE,
            'sample_size': len(feedback_records),
        }

    return {'updated': False, 'reason': '数据分布不足', 'temperature': DEFAULT_TEMPERATURE}


# ══════════════════════════════════════════
# 5. 便捷入口
# ══════════════════════════════════════════

def apply_calibration(match: dict) -> dict:
    """对单个匹配结果应用置信度校准

    在九维评估 → 严格上限之后调用此函数，
    将原始置信度替换为校准后的最终置信度
    """
    raw_conf = match.get('confidence', 50)
    calib = calibrate_confidence(raw_conf)

    match['confidence'] = calib['final']
    match['confidence_raw'] = calib['raw']
    match['confidence_calibrated'] = True
    match['calibration_steps'] = calib['steps']
    match['calibration_temperature'] = calib['temperature']

    # 重算 decision (可能因校准变化)
    final = calib['final']
    match['decision'] = 'high' if final >= 95 else ('medium' if final >= 60 else 'low')

    return match
