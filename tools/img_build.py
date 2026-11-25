"""록맨 11 그림 글자 한국어화.

1) 타이틀 로고(title.arc ui\\03_menu\\title\\tex\\title_jpn_ID, BC7): 부제 「運命の歯車!!」 → 「운명의 톱니바퀴!!」
   텍스처 1024² 안에 세 층: 0~255행 본 로고, 256~511행 = 본 로고 알파 실루엣(흰색), 512~767행 = 실루엣 흐림.
   부제는 배너 파란 띠 아래쪽 직선 경계 밑에만 있다 → 경계 밑을 비우고 새 부제를 그린 뒤 2·3층은 차분만 반영.
2) 보스 소개(briefing00N.arc ui\\02_ingame\\intro\\tex\\name0K_jpn_BM_NOMIP, BC7): 윗줄 오른쪽 가타카나 이름 → 한글
   0~255행 = 그림, 233~ 행 = 검은 그림자(위 그림 알파를 +234행, 흐림 5·세기 4 로 근사).

build() → {arc 경로: {(항목 이름, 타입 해시): 새 바이트}}
"""
import os
import sys

import etcpak
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deswizzle  # noqa: E402
import mtarc      # noqa: E402
import mttex11    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '_work', 'romfs', 'nativeNXx64', 'arc')
FONT_DIR = os.path.join(os.path.dirname(ROOT), '폰트', 'S-Core_Dream_OTF')
TEX_HASH = 0x241f5deb
BS = chr(92)
SS = 4          # 초표본 배율

BOSS_KO = ['블록맨', '애시드맨', '파일맨', '러버맨', '퓨즈맨', '툰드라맨', '토치맨', '블래스트맨']


def tex_get(arc, suffix):
    d, _, _, es = mtarc.parse(arc)
    e = next(e for e in es if e['name'].endswith(suffix) and e['hash'] == TEX_HASH)
    return e['name'], mtarc.blob(d, e)


def tex_encode_bc7(head, im):
    """RGBA 그림 → 같은 머리의 BC7 텍스처 (밉 1단계만 있는 텍스처 전용)."""
    i = mttex11.info(head)
    assert i['mips'] == 1 and i['fmt'] == 0x30, i
    w, h = im.size
    assert (w, h) == (i['w'], i['h'])
    blocks = etcpak.compress_bc7(im.convert('RGBA').tobytes(), w, h)
    wb, hb = w // 4, h // 4
    sw = deswizzle.swizzle(blocks, wb, hb, 16, mttex11.block_height(hb))
    size, *_ = mttex11.level_size(w, h, 0x30)
    assert len(sw) == size, (len(sw), size)
    out = head[:24] + sw
    back = np.array(mttex11.decode(out)).astype(int)
    err = np.abs(back - np.array(im.convert('RGBA')).astype(int)).mean()
    if err > 3:
        raise SystemExit(f'BC7 되읽기 오차 과다 {err:.2f}')
    return out


def text_mask(text, font, shear, track=0, sx=1.0):
    """글자 마스크(초표본, L). 기울임 shear(아래가 왼쪽), 자간 track(초표본 px), 가로 배율 sx."""
    parts = []
    for ch in text:
        l, t, r, b = font.getbbox(ch, anchor='ls')
        parts.append((ch, l, t, r, b, font.getlength(ch)))
    asc = -min(p[2] for p in parts)
    desc = max(p[4] for p in parts)
    width = int(sum(p[5] for p in parts) + track * (len(parts) - 1) + 4 * SS)
    H = asc + desc + 4 * SS
    im = Image.new('L', (width, H), 0)
    dr = ImageDraw.Draw(im)
    x = 2 * SS
    for ch, l, t, r, b, adv in parts:
        dr.text((x, 2 * SS + asc), ch, font=font, fill=255, anchor='ls')
        x += adv + track
    if sx != 1.0:
        im = im.resize((max(1, int(im.width * sx)), im.height), Image.LANCZOS)
    pad = int(H * shear) + 2
    W2 = im.width + pad
    im2 = Image.new('L', (W2, H), 0)
    im2.paste(im, (0, 0))          # 위쪽이 오른쪽으로 밀리므로 여백은 오른쪽에(왼쪽에 두면 마지막 글자 오른쪽 위가 잘린다, 11/25)
    # x' = x - shear*(y - H): 위쪽이 오른쪽으로
    im2 = im2.transform((W2, H), Image.AFFINE, (1, shear, -shear * H, 0, 1, 0), Image.BICUBIC)
    bb = im2.getbbox()
    return im2.crop(bb)


def dilate(mask, r):
    if r <= 0:
        return mask
    return mask.filter(ImageFilter.MaxFilter(2 * r + 1))


# ── 1) 타이틀 로고 부제 ──
SUB_TEXT = '운명의 톱니바퀴!!'
SUB_BOX = (352, 168, 706, 236)       # 부제가 놓이는 영역(텍스처 좌표)
SUB_COLOR_OUT = (59, 79, 160)        # 원본 부제 테두리 색(측정값으로 덮어씀)


def band_line():
    """배너 파란 띠 아래 경계: 부제 왼쪽(x 290~350)에서 잰 직선 y = 202 - 0.1833*(x - 290) (실측)."""
    return -0.18333, 202 + 0.18333 * 290


SUB_FIT = (365, 175, 690, 219)       # 새 부제(테두리 포함)를 맞춰 넣을 상자; 원본 부제 오른쪽 끝 x≈693


def build_title():
    arc = os.path.join(SRC, 'title.arc')
    name, t = tex_get(arc, BS + 'title_jpn_ID')
    im = mttex11.decode(t)
    J = np.array(im).astype(np.float64)
    A = J[..., 3]
    a, b = band_line()
    x0, y0, x1, y1 = SUB_BOX
    yy, xx = np.mgrid[0:1024, 0:1024]
    # 옛 부제 = 띠 경계선 아래, 그리고 171 행 아래(그 위는 로고 글자 그림자) — 열별 불투명 구간 실측(11/25)
    below = (yy > np.maximum(a * xx + b, 171)) & (xx >= x0) & (xx < x1) & (yy < y1)
    region = J[below & (A > 250)]
    nonwhite = region[region[:, :3].sum(1) < 600]
    out_col = tuple(int(v) for v in np.median(nonwhite[:, :3], 0))
    old_alpha1 = A[0:256].copy()
    J[below] = 0
    # 띠와 겹친 옛 부제의 흰 조각(경계선 바로 위 8행) → 띠 색
    near = (yy > a * xx + b - 8) & (yy <= a * xx + b + 1) & (xx >= x0) & (xx < 450) & (np.abs(J[..., :3] - np.array(out_col)).sum(2) > 60) & (J[..., :3].sum(2) > 330)
    J[near, :3] = out_col
    if np.abs(J[150:240, 352:706, 3][J[150:240, 352:706, 3] > 0]).size == 0:
        raise SystemExit('부제 지우기가 띠까지 지웠다')
    font = ImageFont.truetype(os.path.join(FONT_DIR, 'SCDream9.otf'), 46 * SS)
    g = text_mask(SUB_TEXT, font, 0.22, track=-1 * SS, sx=0.9)
    g = g.resize((g.width // SS, g.height // SS), Image.LANCZOS)
    ro = 4
    fx0, fy0, fx1, fy1 = SUB_FIT
    th = (fy1 - fy0) - 2 * ro
    sc = th / g.height
    nw = round(g.width * sc)
    if nw > (fx1 - fx0) - 2 * ro:
        nw = (fx1 - fx0) - 2 * ro                        # 가로를 좁혀 상자에 맞춤
    g = g.resize((nw, th), Image.LANCZOS)
    pad = ro + 2
    gm = Image.new('L', (g.width + 2 * pad, g.height + 2 * pad), 0)
    gm.paste(g, (pad, pad))
    outline = dilate(gm, ro).filter(ImageFilter.GaussianBlur(0.6))
    W, H = gm.size
    px = (fx0 + fx1) // 2 - W // 2
    py = (fy0 + fy1) // 2 - H // 2
    layer = np.zeros((H, W, 4))
    oa = np.array(outline).astype(np.float64) / 255
    ga = np.array(gm).astype(np.float64) / 255
    for c in range(3):
        layer[..., c] = out_col[c] * (1 - ga) + 255 * ga
    layer[..., 3] = np.maximum(oa, ga) * 255
    sub = J[py:py + H, px:px + W]
    yy2, xx2 = np.mgrid[py:py + H, px:px + W]
    ok = (yy2 > a * xx2 + b - 6)                         # 띠 위(배너 안쪽)로는 그리지 않음
    la = layer[..., 3:4] / 255 * ok[..., None]
    sub[..., :3] = layer[..., :3] * la + sub[..., :3] * (1 - la)
    sub[..., 3] = np.maximum(sub[..., 3], layer[..., 3] * ok)
    J[py:py + H, px:px + W] = sub
    new_alpha1 = J[0:256, :, 3].copy()
    J[256:512, :, :3] = 255
    J[256:512, :, 3] = new_alpha1
    blur = lambda m: np.clip(np.array(Image.fromarray(np.clip(m, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))).astype(float) * 2, 0, 255)
    # 3층: 부제 주변만 흐림 모델로 새로 만들고 가장자리를 부드럽게 섞는다(차분 방식은 고리 잔상이 남았다)
    model = blur(new_alpha1)
    wgt = np.zeros((256, 1024))
    wgt[150 - 0:250, 330:735] = 1
    wgt = np.array(Image.fromarray((wgt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))).astype(float) / 255
    J[512:768, :, 3] = np.clip(J[512:768, :, 3] * (1 - wgt) + model * wgt, 0, 255)
    res = Image.fromarray(np.clip(J + 0.5, 0, 255).astype(np.uint8), 'RGBA')
    res.save(os.path.join(ROOT, '_work', 'img', 'out_title_jpn.png'))
    return {arc: {(name, TEX_HASH): tex_encode_bc7(t, res)}}


# ── 2) 보스 소개 이름 ──
KANA_Y = (0, 90)          # 윗줄 가타카나 행 범위
KANA_X0 = 520             # 이보다 오른쪽 (DWN 번호는 330 왼쪽)
SHADOW_OFF = 234
SHADOW_BLUR, SHADOW_GAIN = 5, 3


def kana_style(J, x0, x1):
    """원본 가타카나의 바깥 흰 테두리·파란 테두리·채움 잡티 표본."""
    reg = J[KANA_Y[0]:KANA_Y[1], x0:x1].reshape(-1, 4)
    op = reg[reg[:, 3] > 250]
    blue = op[(op[:, 2] > 200) & (op[:, 0] < 80)]
    fill = op[(op[:, :3].min(1) > 200)]
    return np.median(blue[:, :3], 0), fill[:, :3]


def build_names():
    out = {}
    font = ImageFont.truetype(os.path.join(FONT_DIR, 'SCDream8.otf'), 58 * SS)
    rng = np.random.default_rng(11)
    for k, ko in enumerate(BOSS_KO):
        arc = os.path.join(SRC, 'briefing', 'briefing%03d.arc' % (k + 1))
        name, t = tex_get(arc, BS + 'name%02d_jpn_BM_NOMIP' % k)
        im = mttex11.decode(t)
        J = np.array(im).astype(np.float64)
        A = J[..., 3]
        top = A[KANA_Y[0]:KANA_Y[1], KANA_X0:]
        cols = np.nonzero(top.max(0) > 0)[0]
        rows = np.nonzero(top.max(1) > 0)[0]
        kx0, kx1 = KANA_X0 + cols.min(), KANA_X0 + cols.max() + 1
        ky0, ky1 = KANA_Y[0] + rows.min(), KANA_Y[0] + rows.max() + 1
        blue, fills = kana_style(J, kx0, kx1)
        old_top = np.zeros((256, 1024))
        old_top[KANA_Y[0]:KANA_Y[1], KANA_X0:] = A[KANA_Y[0]:KANA_Y[1], KANA_X0:]
        J[KANA_Y[0]:KANA_Y[1], KANA_X0:] = 0
        # 새 이름: 글자 사이를 원본처럼 넉넉히
        g = text_mask(ko, font, 0.18, track=14 * SS)
        g = g.resize((g.width // SS, g.height // SS), Image.LANCZOS)
        # 높이를 원본 가타카나 잉크 높이(테두리 제외)에 맞춤
        target_h = (ky1 - ky0) - 2 * 5
        sc = target_h / g.height
        g = g.resize((max(1, round(g.width * sc)), target_h), Image.LANCZOS)
        pad = 6
        gm = Image.new('L', (g.width + 2 * pad, g.height + 2 * pad), 0)
        gm.paste(g, (pad, pad))
        m_blue = dilate(gm, 3)
        m_out = dilate(gm, 5).filter(ImageFilter.GaussianBlur(0.7))
        W, H = gm.size
        px = kx1 - W + 1                                 # 오른쪽 끝을 원본에 맞춤
        py = ky0 - (H - (ky1 - ky0)) // 2
        if px < KANA_X0:
            raise SystemExit(f'보스 이름이 너무 길다: {ko} {W}px')
        ga = np.array(gm).astype(float) / 255
        ba = np.array(m_blue).astype(float) / 255
        oa = np.array(m_out).astype(float) / 255
        noise = fills[rng.integers(0, len(fills), size=(H, W))]
        col = np.zeros((H, W, 3))
        col[:] = 255
        col = col * (1 - ba[..., None]) + blue * ba[..., None]
        col = col * (1 - ga[..., None]) + noise * ga[..., None]
        J[py:py + H, px:px + W, :3] = col
        J[py:py + H, px:px + W, 3] = oa * 255
        # 그림자: 옛 이름 그림자 영역을 비우고 새 이름 그림자
        new_top = np.zeros((256, 1024))
        new_top[KANA_Y[0]:KANA_Y[1], KANA_X0:] = J[KANA_Y[0]:KANA_Y[1], KANA_X0:, 3]
        sh = lambda m: np.clip(np.array(Image.fromarray(m.astype(np.uint8)).filter(ImageFilter.GaussianBlur(SHADOW_BLUR))).astype(float) * SHADOW_GAIN, 0, 255)
        s_old, s_new = sh(old_top), sh(new_top)
        r0, r1 = SHADOW_OFF + KANA_Y[0], min(512, SHADOW_OFF + KANA_Y[1] + 12)
        if r1 > 322:
            r1 = 322                                     # 큰 이름 그림자(324 행~)는 건드리지 않음
        seg = J[r0:r1, KANA_X0 - 12:, 3]
        src_rows = slice(r0 - SHADOW_OFF, r1 - SHADOW_OFF)
        seg[:] = np.clip(seg - s_old[src_rows, KANA_X0 - 12:] + s_new[src_rows, KANA_X0 - 12:], 0, 255)
        # 남은 옛 그림자 찌꺼기: 새 그림자보다 진한 곳은 새 그림자로
        seg[:] = np.where(s_old[src_rows, KANA_X0 - 12:] > 8, s_new[src_rows, KANA_X0 - 12:], seg)
        J[r0:r1, KANA_X0 - 12:, :3] = 0
        res = Image.fromarray(np.clip(J + 0.5, 0, 255).astype(np.uint8), 'RGBA')
        res.save(os.path.join(ROOT, '_work', 'img', 'out_name%02d.png' % k))
        out[arc] = {(name, TEX_HASH): tex_encode_bc7(t, res)}
    return out


# ── 3) 일본판 시작 경고 「ご注意」(logo.arc illegalcopy_ID_HQ, 1920x1080 BC3: RGB=(123,255,123), 글자는 알파) ──
NOTICE_TITLE = '주의'
NOTICE_LINES = [
    '게임 소프트웨어를 권리자의 허락 없이 인터넷을 통해',
    '전송·배포하는 행위, 또한 불법 인터넷 전송임을',
    '알면서 다운로드하는 행위는 일본국의 법률로',
    '엄격히 금지되어 있습니다.',
    '여러분의 이해와 협조를 부탁드립니다.',
]
# 원본 측정(11/25): 제목 241~321행, 본문 큰 글자 줄 444~489, 541~586, 636~682, 734~779, 829~875 (후리가나 줄은 그 위)
NOTICE_TITLE_BOX = (241, 321)
NOTICE_ROWS = [(444, 489), (541, 586), (636, 682), (734, 779), (829, 875)]
NOTICE_MAXW = 1100


def tex_encode_bc3_alpha(head, im):
    i = mttex11.info(head)
    assert i['mips'] == 1 and i['fmt'] == 0x2a, i
    w, h = im.size
    blocks = etcpak.compress_bc3(im.convert('RGBA').tobytes(), w, h)
    wb, hb = w // 4, h // 4
    sw = deswizzle.swizzle(blocks, wb, hb, 16, mttex11.block_height(hb))
    size, *_ = mttex11.level_size(w, h, 0x2a)
    assert len(sw) == size, (len(sw), size)
    out = head[:24] + sw
    back = np.array(mttex11.decode(out))[..., 3].astype(int)
    err = np.abs(back - np.array(im)[..., 3].astype(int)).mean()
    if err > 3:
        raise SystemExit(f'BC3 되읽기 오차 과다 {err:.2f}')
    return out


def line_img(text, font, ink_h):
    """한 줄을 그려 잉크 높이 ink_h 로 맞춘 L 그림."""
    l, t, r, b = font.getbbox(text, anchor='ls')
    im = Image.new('L', (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=font, fill=255, anchor='ls')
    im = im.crop(im.getbbox())
    # 기준: 한글 '한' 잉크 높이 → ink_h
    pr = Image.new('L', (400, 400), 0)
    ImageDraw.Draw(pr).text((50, 300), '한', font=font, fill=255, anchor='ls')
    hb = pr.getbbox()
    sc = ink_h / (hb[3] - hb[1])
    return im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS), sc, hb


def build_notice():
    arc = os.path.join(SRC, 'logo.arc')
    name, t = tex_get(arc, BS + 'illegalcopy_ID_HQ')
    im = np.array(mttex11.decode(t))
    a = np.zeros(im.shape[:2], np.float64)
    peak = int(im[..., 3].max())                 # 원본 글자 알파 최댓값(221)
    big = ImageFont.truetype(os.path.join(FONT_DIR, 'SCDream7.otf'), 160)
    body = ImageFont.truetype(os.path.join(FONT_DIR, 'SCDream5.otf'), 120)

    def put(img, cy):
        x0 = 960 - img.width // 2
        y0 = cy - img.height // 2
        arr = np.array(img).astype(np.float64)
        a[y0:y0 + img.height, x0:x0 + img.width] = np.maximum(a[y0:y0 + img.height, x0:x0 + img.width], arr)

    y0, y1 = NOTICE_TITLE_BOX
    ti, _, _ = line_img(NOTICE_TITLE, big, (y1 - y0) * 0.95)
    put(ti, (y0 + y1) // 2)
    for text, (r0, r1) in zip(NOTICE_LINES, NOTICE_ROWS):
        li, _, _ = line_img(text, body, (r1 - r0) * 0.93)
        if li.width > NOTICE_MAXW:
            li = li.resize((NOTICE_MAXW, li.height), Image.LANCZOS)
        put(li, (r0 + r1) // 2 - 10)            # 후리가나가 없어진 만큼 살짝 위로
    out = im.copy()
    out[..., 0] = 123
    out[..., 1] = 255
    out[..., 2] = 123
    out[..., 3] = np.clip(a * peak / 255 + 0.5, 0, 255).astype(np.uint8)
    res = Image.fromarray(out, 'RGBA')
    res.save(os.path.join(ROOT, '_work', 'img', 'out_notice.png'))
    return {arc: {(name, TEX_HASH): tex_encode_bc3_alpha(t, res)}}


def build():
    out = {}
    for part in (build_title(), build_names(), build_notice()):
        for k, v in part.items():
            out.setdefault(k, {}).update(v)
    print(f'  그림: arc {len(out)}개, 텍스처 {sum(len(v) for v in out.values())}장')
    return out


if __name__ == '__main__':
    build()
