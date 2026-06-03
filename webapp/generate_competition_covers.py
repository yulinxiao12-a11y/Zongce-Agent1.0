# -*- coding: utf-8 -*-
"""根据设计参考生成学科竞赛盾徽封面图（960×540）
参考: 材料/页面设计参考/ - 盾形徽章 + 竞赛名称
分析提取: 盾牌轮廓(外框深蓝,内填浅色) + 顶部铆钉装饰 + 中部横幅 + 底部尖角
"""
import os, sys, math
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFont
from competitions_data import COMPETITIONS

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'frontend', 'public', 'competition-covers')

W, H = 960, 540

# ── 设计参考提取配色 ──
SHIELD_BORDER  = (29, 78, 215, 230)   # 盾牌外框深蓝
SHIELD_FILL    = (230, 242, 255, 220) # 盾牌填充浅蓝
BANNER_BLUE    = (29, 78, 215, 210)   # 横幅深蓝
BG_TOP         = (240, 247, 255)      # 卡片背景极浅蓝
BG_BOTTOM      = (232, 241, 253)      # 卡片背景稍深
TEXT_DARK      = (29, 78, 215, 255)   # 文字深蓝
TEXT_WHITE     = (255, 255, 255, 255) # 横幅白字
DECO_SHAPE     = (29, 78, 215, 40)    # 装饰形状半透


def load_font(size, bold=False):
    fps = [('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc'),
           'C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/simsun.ttc']
    for fp in fps:
        if os.path.exists(fp):
            try: return ImageFont.truetype(fp, size)
            except: continue
    return ImageFont.load_default()


def generate_cover(comp, out_path):
    is_national = '国家级' in comp.get('level', '')
    level_text = comp.get('level', '').replace('A类', 'A类').replace('B类', 'B类') or ('国家级A类' if is_national else '省级A类')

    img = Image.new('RGBA', (W, H), BG_TOP + (255,))
    draw = ImageDraw.Draw(img)

    # ── 渐变背景 ──
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0]-BG_TOP[0])*t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1]-BG_TOP[1])*t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2]-BG_TOP[2])*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))

    # ── 装饰背景光晕 ──
    for radius in range(150, 320, 14):
        a = int(10*(1-(radius-150)/170))
        draw.ellipse([W-radius-40, -radius+100, W+radius-40, radius+100],
                     fill=DECO_SHAPE[:3]+(max(0,min(255,a)),), outline=None)
    for radius in range(80, 200, 16):
        a = int(8*(1-(radius-80)/120))
        draw.ellipse([-radius+20, H-radius-40, radius+20, H+radius-40],
                     fill=DECO_SHAPE[:3]+(max(0,min(255,a)),), outline=None)

    # ── 左上角级别标签 ──
    tag_font = load_font(22, bold=True)
    tp, tpy = 16, 8
    tb = tag_font.getbbox(level_text)
    tw, th = tb[2]-tb[0]+tp*2, tb[3]-tb[1]+tpy*2
    tx, ty = 42, 38
    draw.rounded_rectangle([tx,ty,tx+tw,ty+th], radius=10, fill=SHIELD_BORDER)
    draw.text((tx+tp, ty+tpy-2), level_text, fill=TEXT_WHITE, font=tag_font)

    # ══════════════════════════════════════════════
    # 盾形徽章 (Shield Emblem)
    # 参考设计: 顶部弧形 + 两侧直线下收 + 底部尖角
    # ══════════════════════════════════════════════

    sx = 200            # shield center X (left portion of card)
    sy = H // 2 - 10    # shield center Y
    sw = 180            # shield width at widest
    sh = 260            # shield total height

    # 盾牌轮廓坐标
    shield_top = sy - sh//2       # y at top of shield
    shield_bot = sy + sh//2       # y at pointed bottom
    shield_mid = sy + sh//6       # y where sides start narrowing

    # 盾牌路径（从上到下）:
    # 1. 顶部弧形拱
    # 2. 两侧垂直向下
    # 3. 下半部收窄到尖角
    arc_radius = sw * 0.7
    arc_top = shield_top - 10

    # 用椭圆画顶部弧形
    draw.arc([sx-arc_radius, arc_top-20, sx+arc_radius, arc_top+arc_radius],
             start=180, end=360, fill=SHIELD_BORDER, width=3)

    # 盾牌主体: 用多边形
    mid_y = shield_top + arc_radius//2 + 10
    narrow_start = shield_top + sh * 0.55
    shield_pts = [
        # 左上角（弧线终点）
        (sx - sw//2 + 5, mid_y),
        # 左边垂直
        (sx - sw//2 + 5, narrow_start),
        # 左下收窄
        (sx - sw//6, shield_bot - 20),
        # 底部尖角
        (sx, shield_bot),
        # 右下收窄
        (sx + sw//6, shield_bot - 20),
        # 右边垂直
        (sx + sw//2 - 5, narrow_start),
        # 右上角
        (sx + sw//2 - 5, mid_y),
    ]

    # 盾牌内填充
    inner_pts = [(px-4 if i in (0,3,6) else px+4 if i in (3,) else px,
                  py-4 if i in (0,6) else py+4 if i==3 else py)
                 for i, (px, py) in enumerate(shield_pts)]
    # Fix: shift all inner points inward
    inner_pts = [
        (sx - sw//2 + 18, mid_y + 5),      # top-left inner
        (sx - sw//2 + 18, narrow_start - 5), # left inner
        (sx - sw//8, shield_bot - 28),      # bottom-left inner
        (sx, shield_bot - 6),               # bottom inner point
        (sx + sw//8, shield_bot - 28),      # bottom-right inner
        (sx + sw//2 - 18, narrow_start - 5), # right inner
        (sx + sw//2 - 18, mid_y + 5),       # top-right inner
    ]

    # 盾牌外框
    draw.polygon(shield_pts, fill=SHIELD_FILL, outline=SHIELD_BORDER)

    # ── 顶部铆钉装饰 ──
    rivet_r = 7
    draw.ellipse([sx-rivet_r-16, shield_top+8-rivet_r,
                  sx-rivet_r+16, shield_top+8+rivet_r],
                 fill=SHIELD_BORDER[:3]+(180,), outline=None)
    draw.ellipse([sx-rivet_r+16, shield_top+8-rivet_r,
                  sx-rivet_r+48, shield_top+8+rivet_r],
                 fill=SHIELD_BORDER[:3]+(180,), outline=None)

    # ── 中部横幅 (Banner across shield) ──
    banner_y = sy + sh//8
    banner_h = 42
    banner_w = sw - 30
    draw.rounded_rectangle(
        [sx-banner_w//2, banner_y, sx+banner_w//2, banner_y+banner_h],
        radius=6, fill=BANNER_BLUE,
    )
    # 横幅左右折角
    fold_w = 14
    draw.polygon(
        [(sx-banner_w//2, banner_y), (sx-banner_w//2-fold_w, banner_y+banner_h//2),
         (sx-banner_w//2, banner_y+banner_h)],
        fill=BANNER_BLUE,
    )
    draw.polygon(
        [(sx+banner_w//2, banner_y), (sx+banner_w//2+fold_w, banner_y+banner_h//2),
         (sx+banner_w//2, banner_y+banner_h)],
        fill=BANNER_BLUE,
    )

    # ── 竞赛名称（右半部分） ──
    text_x = sx + sw//2 + 30
    max_tw = W - text_x - 50
    name = comp.get('name', '')
    name_font = load_font(36, bold=True)

    lines = []
    cur = ''
    for ch in name:
        test = cur + ch
        bb = name_font.getbbox(test)
        if bb[2]-bb[0] <= max_tw:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = ch
    if cur: lines.append(cur)
    if len(lines) > 3: lines = lines[:3]; lines[-1] = lines[-1][:-1]+'…'

    lh = 54
    th = len(lines)*lh
    y0 = (H-th)//2 - 10
    for i, line in enumerate(lines):
        draw.text((text_x, y0+i*lh), line, fill=TEXT_DARK, font=name_font)

    # ── 分隔线 + 主办单位 ──
    sep_y = y0 + th + 18
    draw.line([(text_x, sep_y), (text_x+200, sep_y)], fill=SHIELD_BORDER[:3]+(80,), width=1)
    org = comp.get('organizer','').strip()
    if org and len(org) > 2:
        ofont = load_font(18)
        otxt = org if len(org)<32 else org[:30]+'…'
        draw.text((text_x, sep_y+12), otxt, fill=SHIELD_BORDER[:3]+(120,), font=ofont)

    # ── 右下角"学科竞赛" ──
    bf = load_font(15)
    bb_ = bf.getbbox('学科竞赛')
    draw.text((W-bb_[2]+bb_[0]-40, H-40), '学科竞赛', fill=SHIELD_BORDER[:3]+(70,), font=bf)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, 'PNG', optimize=True)
    return out_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.png'): os.remove(os.path.join(OUTPUT_DIR, f))
    ok = fail = 0
    for comp in COMPETITIONS:
        cid = comp.get('id','')
        try:
            generate_cover(comp, os.path.join(OUTPUT_DIR, f'{cid}.png'))
            ok += 1
        except Exception as e:
            fail += 1; print(f'FAIL {cid}: {e}')
    print(f'Generated {ok} covers ({fail} failed) at {OUTPUT_DIR}')
    print(f'{W}×{H} | Shield emblem + competition name | matches design reference')


if __name__ == '__main__':
    main()
