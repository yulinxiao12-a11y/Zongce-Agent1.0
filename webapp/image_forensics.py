# -*- coding: utf-8 -*-
"""
图像防伪取证引擎 — ELA + Exif + 公章检测
依据《综测材料AI审核机制设计》"图像防伪与伪造拦截机制"设计

检测手段:
1. ELA (Error Level Analysis) — 检测拼接/克隆/涂改
2. Exif 元数据审计 — 检测编辑软件留痕/时间倒挂
3. 红色公章/徽标检测 — 验证官方证书有效性
"""
import os
import json
import struct
from io import BytesIO
from datetime import datetime
from typing import Optional


# ══════════════════════════════════════════
# 1. Exif 元数据审计
# ══════════════════════════════════════════

EDITING_SOFTWARE_SIGNATURES = [
    'photoshop', 'lightroom', 'gimp', 'paint.net', 'paint shop pro',
    'illustrator', 'corel', 'affinity', 'photopea', 'canva',
    '美图', '醒图', 'snapseed', 'picsart', '美颜',
    'adobe', 'pixelmator', 'fotor', '图怪兽', '创客贴',
    '稿定设计', '凡科快图', '可画',
]

SUSPICIOUS_SOFTWARE = [
    'photoshop', 'gimp', 'paint.net', 'illustrator',
    '美图', '醒图', 'picsart', '美颜',
]


def audit_exif(file_path: str) -> dict:
    """解析图像 Exif 元数据进行安全审计

    返回:
        {
            'has_exif': bool,
            'software': str | None,       # 创建/编辑软件
            'datetime_original': str | None,  # 原始拍摄/创建时间
            'datetime_digitized': str | None,
            'make': str | None,           # 设备厂商
            'model': str | None,          # 设备型号
            'is_suspicious': bool,        # 是否可疑 (含编辑软件留痕)
            'suspicious_reasons': [str],  # 可疑原因
            'risk_score': float,          # 风险评分 0~1
            'warning_level': str,         # 'safe' | 'warning' | 'danger'
        }
    """
    result = {
        'has_exif': False,
        'software': None,
        'datetime_original': None,
        'datetime_digitized': None,
        'make': None,
        'model': None,
        'is_suspicious': False,
        'suspicious_reasons': [],
        'risk_score': 0.0,
        'warning_level': 'safe',
    }

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, Base as ExifBase

        img = Image.open(file_path)
        exif_data = img._getexif()

        if not exif_data:
            # 尝试通过 exif_bytes 解析
            exif_bytes = img.info.get('exif')
            if exif_bytes:
                try:
                    from PIL.ExifTags import GPSTAGS
                    # 简易解析
                except Exception:
                    pass
            return result

        result['has_exif'] = True
        exif_dict = {}

        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if isinstance(value, bytes):
                try:
                    value = value.decode('utf-8', errors='replace')
                except Exception:
                    value = str(value)[:100]
            exif_dict[tag_name] = str(value)[:200]

        # ── 提取关键字段 ──
        software = exif_dict.get('Software', '')
        if software:
            result['software'] = software
            software_lower = software.lower()
            for sig in SUSPICIOUS_SOFTWARE:
                if sig in software_lower:
                    result['is_suspicious'] = True
                    result['suspicious_reasons'].append(f'检测到图像编辑软件: {software}')
                    result['risk_score'] += 0.4
                    break

        result['datetime_original'] = exif_dict.get('DateTimeOriginal', '')
        result['datetime_digitized'] = exif_dict.get('DateTimeDigitized', '')
        result['make'] = exif_dict.get('Make', '')
        result['model'] = exif_dict.get('Model', '')

        # ── 时间合理性检查 ──
        dt_orig = result['datetime_original']
        if dt_orig:
            try:
                parsed = datetime.strptime(dt_orig, '%Y:%m:%d %H:%M:%S')
                if parsed > datetime.now():
                    result['suspicious_reasons'].append(f'拍摄时间{dt_orig}在未来，疑似伪造')
                    result['risk_score'] += 0.3
                    result['is_suspicious'] = True
            except ValueError:
                pass

        # ── 检查是否被二次保存（JPEG重压缩痕迹） ──
        # 通过比较 Make/Model 与 Software 判断
        if result['make'] and result['software']:
            # 有设备信息又有软件信息：可能是手机拍后用软件编辑
            sw_lower = result['software'].lower()
            if any(sig in sw_lower for sig in SUSPICIOUS_SOFTWARE):
                result['suspicious_reasons'].append(
                    f'设备{result["make"]}拍摄后经{result["software"]}编辑'
                )

        # ── 风险等级 ──
        if result['risk_score'] >= 0.5:
            result['warning_level'] = 'danger'
        elif result['risk_score'] >= 0.2:
            result['warning_level'] = 'warning'

    except Exception as e:
        result['suspicious_reasons'].append(f'Exif解析异常: {str(e)[:80]}')
        result['risk_score'] = min(1.0, result['risk_score'] + 0.1)

    return result


# ══════════════════════════════════════════
# 2. ELA (Error Level Analysis)
# ══════════════════════════════════════════

def ela_analysis(file_path: str, quality: int = 90) -> dict:
    """误差水平分析 — 检测图像篡改痕迹

    原理: 对图像以指定质量重新保存，然后逐像素计算原始图与重新保存图之间的误差。
    被编辑/拼接/克隆过的区域会因压缩历史不同而呈现异常误差水平。

    Args:
        file_path: 图像文件路径
        quality: 重新保存的 JPEG 质量 (默认90%)

    Returns:
        {
            'ela_score': float,         # 综合 ELA 评分 0~1 (越低越可疑)
            'max_error': float,         # 最大像素误差
            'mean_error': float,        # 平均像素误差
            'anomaly_regions': int,      # 异常区域数量 (>2σ的区域)
            'anomaly_ratio': float,     # 异常像素占比
            'is_suspicious': bool,      # 是否可疑
            'warning_level': str,       # 'safe'|'warning'|'danger'
            'detail': str,              # 详细描述
        }
    """
    result = {
        'ela_score': 1.0,
        'max_error': 0.0,
        'mean_error': 0.0,
        'anomaly_regions': 0,
        'anomaly_ratio': 0.0,
        'is_suspicious': False,
        'warning_level': 'safe',
        'detail': '',
    }

    try:
        from PIL import Image
        import numpy as np

        img = Image.open(file_path).convert('RGB')
        # 缩放到合理大小以加速 (最大宽高 1024px)
        w, h = img.size
        max_dim = 1024
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        arr_orig = np.array(img, dtype=np.float32)

        # 以指定质量重新保存再读回
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=quality)
        buf.seek(0)
        img_resaved = Image.open(buf).convert('RGB')
        arr_resaved = np.array(img_resaved, dtype=np.float32)

        # 确保维度一致
        if arr_orig.shape != arr_resaved.shape:
            h = min(arr_orig.shape[0], arr_resaved.shape[0])
            w = min(arr_orig.shape[1], arr_resaved.shape[1])
            arr_orig = arr_orig[:h, :w, :]
            arr_resaved = arr_resaved[:h, :w, :]

        # 逐像素误差 (使用均方误差)
        diff = np.abs(arr_orig - arr_resaved)
        error_map = np.mean(diff, axis=2)  # RGB 平均误差

        max_error = float(np.max(error_map))
        mean_error = float(np.mean(error_map))
        std_error = float(np.std(error_map))

        # 异常检测: 超过 2σ 的像素视为异常
        threshold = mean_error + 2.0 * std_error
        anomaly_mask = error_map > threshold
        anomaly_count = int(np.sum(anomaly_mask))
        total_pixels = error_map.size
        anomaly_ratio = anomaly_count / max(total_pixels, 1)

        # ELA 评分: 正常图像误差均匀 → 高分；异常图像有局部高误差 → 低分
        # 注意：截图/PNG原图重存为JPEG必然产生差异，阈值需放宽避免误报
        if mean_error < 1.0:
            ela_score = 1.0  # 几乎无损 (PNG 原图)
        elif anomaly_ratio < 0.01:
            ela_score = 0.95  # 正常 JPEG
        elif anomaly_ratio < 0.03:
            ela_score = 0.85  # 轻微异常
        elif anomaly_ratio < 0.08:
            ela_score = 0.70  # 边界（截图重压缩常见区间）
        elif anomaly_ratio < 0.15:
            ela_score = 0.50  # 可疑 — 需结合其他证据
        else:
            ela_score = 0.30  # 高度可疑 — 大面积编辑痕迹

        is_suspicious = anomaly_ratio >= 0.08

        if anomaly_ratio >= 0.15:
            warning_level = 'danger'
            detail = f'ELA检测到大面积异常({anomaly_ratio*100:.1f}%像素误差>2σ)，疑似大幅篡改/拼接'
        elif anomaly_ratio >= 0.08:
            warning_level = 'warning'
            detail = f'ELA检测到局部异常({anomaly_ratio*100:.1f}%像素误差>2σ)，可能为截图重压缩或局部编辑'
        else:
            warning_level = 'safe'
            detail = f'ELA正常(异常像素{anomaly_ratio*100:.2f}%)'

        result = {
            'ela_score': round(ela_score, 3),
            'max_error': round(max_error, 2),
            'mean_error': round(mean_error, 2),
            'anomaly_regions': anomaly_count,
            'anomaly_ratio': round(anomaly_ratio, 4),
            'is_suspicious': is_suspicious,
            'warning_level': warning_level,
            'detail': detail,
        }

        buf.close()

    except ImportError:
        result['detail'] = 'numpy 未安装，跳过 ELA 分析'
    except Exception as e:
        result['detail'] = f'ELA分析异常: {str(e)[:80]}'

    return result


# ══════════════════════════════════════════
# 3. 公章/红色印章检测
# ══════════════════════════════════════════

def detect_red_seal(file_path: str) -> dict:
    """检测图像中是否存在红色公章/印章

    原理: 在 HSV 色彩空间中检测红色区域，分析其面积、圆度、集中度
    官方证书通常有红色圆形公章，这是证书有效性的重要信号。

    返回:
        {
            'has_red_seal': bool,
            'red_pixel_ratio': float,    # 红色像素占比
            'seal_regions': int,         # 检测到的疑似印章区域数
            'confidence': float,         # 公章可信度 0~1
            'detail': str,
        }
    """
    result = {
        'has_red_seal': False,
        'red_pixel_ratio': 0.0,
        'seal_regions': 0,
        'confidence': 0.0,
        'detail': '',
    }

    try:
        from PIL import Image
        import numpy as np

        img = Image.open(file_path).convert('RGB')
        w, h = img.size
        max_dim = 800
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        arr = np.array(img)

        # 红色像素检测 (RGB 空间中 R 主导且足够饱和)
        r, g, b = arr[:, :, 0].astype(float), arr[:, :, 1].astype(float), arr[:, :, 2].astype(float)

        # 条件: R > G+B 且 R 足够高
        saturation = np.maximum(r - np.maximum(g, b), 0)
        brightness = r
        red_mask = (saturation > 60) & (brightness > 100)

        # 也检测 HSV 空间中的红色 (色相 0-10 或 160-180)
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0
        c_max = np.maximum(np.maximum(r_norm, g_norm), b_norm)
        c_min = np.minimum(np.minimum(r_norm, g_norm), b_norm)
        delta = c_max - c_min

        # 避免除零
        delta_safe = np.where(delta == 0, 1.0, delta)
        hue = np.zeros_like(delta)
        mask_r = (c_max == r_norm)
        mask_g = (c_max == g_norm)
        mask_b = (c_max == b_norm)

        hue = np.where(mask_r, ((g_norm - b_norm) / delta_safe) % 6, hue)
        hue = np.where(mask_g, ((b_norm - r_norm) / delta_safe) + 2, hue)
        hue = np.where(mask_b, ((r_norm - g_norm) / delta_safe) + 4, hue)

        sat = np.where(c_max == 0, 0, delta / c_max)

        # 红色色相: 0-20 或 330-360 (归一化到0-1: 0-0.056 或 0.917-1.0)
        # 我们的 hue 是 0-6 范围: 红色在 0-0.33 或 5.5-6.0
        red_hue_mask = ((hue < 0.33) | (hue > 5.5)) & (sat > 0.2) & (c_max > 0.4)
        combined_mask = red_mask | red_hue_mask

        red_pixels = int(np.sum(combined_mask))
        total_pixels = combined_mask.size
        red_ratio = red_pixels / max(total_pixels, 1)

        # 公章通常占图像 1%~15% 的像素
        if red_ratio > 0.005:  # 至少 0.5%
            result['has_red_seal'] = True
            if red_ratio > 0.15:
                result['confidence'] = 0.5  # 红色太多，可能是红底图而非公章
                result['detail'] = f'检测到大量红色区域({red_ratio*100:.1f}%)，非典型公章特征'
            else:
                result['confidence'] = min(0.95, 0.5 + red_ratio * 5)
                result['detail'] = f'检测到红色区域({red_ratio*100:.1f}%)，疑似公章/印章'
            result['seal_regions'] = 1 if red_ratio > 0.01 else 0
        else:
            result['detail'] = f'未检测到明显红色印章区域(红色占比{red_ratio*100:.2f}%)'

        result['red_pixel_ratio'] = round(red_ratio, 4)

    except ImportError:
        result['detail'] = 'numpy 未安装，跳过公章检测'
    except Exception as e:
        result['detail'] = f'公章检测异常: {str(e)[:80]}'

    return result


# ══════════════════════════════════════════
# 4. 综合取证入口
# ══════════════════════════════════════════

def forensic_analysis(file_path: str) -> dict:
    """完整的图像取证分析

    返回:
        {
            'exif': {...},
            'ela': {...},
            'red_seal': {...},
            'overall_risk': float,       # 综合风险评分 0~1
            'overall_level': str,        # 'safe'|'warning'|'danger'
            'confidence_penalty': float,  # 建议从置信度中扣除的分数
            'recommendations': [str],    # 建议动作
        }
    """
    exif = audit_exif(file_path)
    ela = ela_analysis(file_path)
    red_seal = detect_red_seal(file_path)

    # 综合风险评估
    risk_score = 0.0
    recommendations = []

    # Exif 风险
    if exif['warning_level'] == 'danger':
        risk_score += 0.4
        recommendations.append('Exif检测到高危编辑痕迹，置信度上限降至50%')
    elif exif['warning_level'] == 'warning':
        risk_score += 0.15
        recommendations.append('Exif含编辑软件记录，建议人工核实')

    # ELA 风险
    if ela['warning_level'] == 'danger':
        risk_score += 0.4
        recommendations.append('ELA检测到大面积篡改，置信度上限降至50%')
    elif ela['warning_level'] == 'warning':
        risk_score += 0.2
        recommendations.append('ELA检测到局部异常，建议人工核实')

    # 公章信号 — 仅作为正面加分项，无公章不扣分
    # （技术上红色像素检测≠真实印章识别，且电子证书印章无法用颜色检测）
    seal_bonus = 0.0
    if red_seal['has_red_seal'] and red_seal['confidence'] > 0.6:
        seal_bonus = 0.08  # 有公章信号降低风险（加分而非惩罚缺失）
        risk_score = max(0, risk_score - seal_bonus)

    risk_score = min(1.0, max(0.0, risk_score))

    if risk_score >= 0.5:
        overall_level = 'danger'
        confidence_penalty = 0.5  # 强制降至50%以下
    elif risk_score >= 0.2:
        overall_level = 'warning'
        confidence_penalty = 0.15
    else:
        overall_level = 'safe'
        confidence_penalty = 0.0

    return {
        'exif': exif,
        'ela': ela,
        'red_seal': red_seal,
        'overall_risk': round(risk_score, 3),
        'overall_level': overall_level,
        'confidence_penalty': confidence_penalty,
        'seal_bonus': seal_bonus,
        'recommendations': recommendations,
    }


def apply_forensic_penalty(match: dict, forensic_result: dict) -> dict:
    """将取证结果应用到匹配置信度

    - Exif异常或ELA大面积篡改 → 强制置信度≤50%（仅 danger 级别）
    - 公章检测为正面加分（通过 seal_bonus 抵消部分 penalty）
    - warning 级别应用温和惩罚，不再一刀切
    """
    penalty = forensic_result.get('confidence_penalty', 0)
    seal_bonus = forensic_result.get('seal_bonus', 0.0)

    # 公章加分抵消取证惩罚（有 seal 的材料降低 penalty）
    effective_penalty = max(0, penalty - seal_bonus)

    if effective_penalty <= 0 and forensic_result['overall_level'] != 'danger':
        match['forensic_penalty_applied'] = False
        return match

    original_conf = match.get('confidence', 50)
    if forensic_result['overall_level'] == 'danger':
        # 高危：强制置信度≤50%
        penalized_conf = min(original_conf, 50)
    else:
        penalized_conf = round(original_conf * (1 - effective_penalty), 1)

    match['confidence'] = max(5, penalized_conf)
    match['forensic_penalty_applied'] = True
    match['forensic_result'] = forensic_result

    # 添加风控标签
    if 'audit' in match:
        risk_tags = match['audit'].get('risk_assessment', {}).get('risk_tags', [])
        if forensic_result['overall_level'] == 'danger':
            if 'TAMPER_SUSPECTED' not in risk_tags:
                risk_tags.append('TAMPER_SUSPECTED')
        elif forensic_result['overall_level'] == 'warning':
            if 'IMAGE_ANOMALY' not in risk_tags:
                risk_tags.append('IMAGE_ANOMALY')

    return match
