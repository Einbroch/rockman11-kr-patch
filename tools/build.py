"""록맨 11 (스위치) 한글패치 빌드.

한국어는 일본어 칸(*_jpn)에 넣는다 → 게임 언어 「日本語」(표시는 「한국어」)에서 나온다.
  1) tr/*.txt 번역 원고 → 모든 arc 의 msg\\<이름>_jpn GMD 를 라벨 단위로 교체
  2) 번역에 쓰인 한글을 일본어 글꼴(system·menu·index, language 는 「한국어」만)에 새 페이지로 추가
     (GFD 0x11007, 글꼴이 든 arc 사본 전부)
  3) 그림 글자(tools/img_build.py)
출력: build/romfs/nativeNXx64/... (바뀐 arc 만)

  python tools/build.py [--partial] [--deploy] [--report]
"""
import glob
import json
import os
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arcpack     # noqa: E402
import deswizzle   # noqa: E402
import fonttex     # noqa: E402
import gmd         # noqa: E402
import mtarc       # noqa: E402
from gfd11 import Gfd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '_work', 'romfs')
OUT = os.path.join(ROOT, 'build', 'romfs')
TITLE = '0100B0C0086B0000'
EDEN_MOD = os.path.join(os.path.dirname(ROOT), 'eden emul', 'user', 'load', TITLE, 'KoreanPatch')
FONT_DIR = os.path.join(os.path.dirname(ROOT), '폰트', 'S-Core_Dream_OTF')
BS = chr(92)
GMD_HASH = 0x242bb29a
GFD_HASH = 0x2d462600
TEX_HASH = 0x241f5deb
PAGE = 1024
GAP = 2
TAG = re.compile(r'<[^<>]*>')
FONT_PREFIX = 'ui' + BS + '01_system' + BS + 'font' + BS + 'text' + BS
# 글꼴 → (에스코어 드림 굵기, 대상 글자): 원본 글꼴 굵기와 맞춘다(system=중간 굵은 고딕, menu=아주 굵은 고딕)
FONTS = {
    'system': (6, 'all'),
    'index': (6, 'all'),
    'menu': (8, 'all'),
    'language': (6, 'lang'),
}
LANG_NAME = '한국어'
# 세이브(언어 설정)를 읽기 전 부팅 화면은 본체 언어 → 한국어 본체면 영어 칸이 나온다.
# 그때 보이는 문구(불러오는 중·세이브 오류 등)만 영어 칸에도 한국어로 넣는다(11/25 사용자 지적).
ENG_ALSO = {'flow': None, 'commonmsg': {'SEL_yes_no', 'SEL_yn_sel_no'}}
LANG_GMD = re.compile(r'language_[A-Za-z]{3}$')


# ── 번역 원고 ──
def load_tr():
    """tr/ref/<이름>.txt(원문 JP/EN) + tr/<이름>.json(라벨 → 한국어) → {이름: (번역, 원문)}. 번역 없는 칸은 None."""
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'tr', 'ref', '*.txt'))):
        name = os.path.splitext(os.path.basename(p))[0]
        cur, jp = None, {}
        for ln in open(p, encoding='utf-8').read().splitlines():
            if ln.startswith('## '):
                cur = ln[3:].strip()
            elif ln.startswith('JP: ') and cur:
                jp[cur] = json.loads(ln[4:])
        kp = os.path.join(ROOT, 'tr', name + '.json')
        ko = json.load(open(kp, encoding='utf-8')) if os.path.exists(kp) else {}
        extra = set(ko) - set(jp)
        if extra:
            raise SystemExit(f'원문에 없는 라벨 {name}: {sorted(extra)[:5]}')
        out[name] = ({k: ko.get(k) for k in jp}, jp)
    return out


def check_tags(lab, src, dst):
    a, b = Counter(TAG.findall(src)), Counter(TAG.findall(dst))
    if a != b:
        raise SystemExit(f'태그 불일치 [{lab}]: {src!r} → {dst!r}')
    if '\\r' in dst or '\\n' in dst:
        raise SystemExit(f'글자 그대로의 줄바꿈 [{lab}]: {dst!r}')


def text_chars(s):
    return set(TAG.sub('', s)) - set('\r\n')


def all_arcs():
    return sorted(glob.glob(os.path.join(SRC, '**', '*.arc'), recursive=True))


def apply_gmd(tr, partial):
    changes = defaultdict(dict)
    need = set()
    need_eng = set()
    missing = []
    seen = set()
    for p in all_arcs():
        d, _, _, es = mtarc.parse(p)
        for e in es:
            if e['hash'] == GMD_HASH and LANG_GMD.match(e['name'].split(BS)[-1]) and not e['name'].endswith('_jpn'):
                # 다른 언어의 언어 목록에서도 일본어 칸 이름을 「한국어」로
                g = gmd.Gmd(mtarc.blob(d, e))
                i = g.labels.index('language_1_1')
                if g.texts[i] != '日本語':
                    raise SystemExit(f'언어 목록 1번이 日本語 가 아니다: {p} {e["name"]}')
                g.texts[i] = LANG_NAME
                changes[p][(e['name'], e['hash'])] = g.build()
                continue
            if e['hash'] == GMD_HASH and e['name'].endswith('_eng') and e['name'].split(BS)[-1][:-4] in ENG_ALSO:
                short = e['name'].split(BS)[-1][:-4]
                want = ENG_ALSO[short]
                rows = tr[short][0]
                g = gmd.Gmd(mtarc.blob(d, e))
                for i, (lab, t) in enumerate(zip(g.labels, g.texts)):
                    if lab in rows and rows[lab] and (want is None or lab in want) and t != 'HARDUMMY':
                        check_tags(lab, t, rows[lab])
                        g.texts[i] = rows[lab]
                        need_eng |= text_chars(rows[lab])
                changes[p][(e['name'], e['hash'])] = g.build()
                continue
            if e['hash'] != GMD_HASH or not e['name'].endswith('_jpn'):
                continue
            short = e['name'].split(BS)[-1][:-4]
            if short not in tr:
                continue
            rows, jp = tr[short]
            g = gmd.Gmd(mtarc.blob(d, e))
            hit = False
            labels = g.labels or ['#%d' % i for i in range(len(g.texts))]   # 라벨 없는 GMD(scn_name)는 순번
            for i, (lab, t) in enumerate(zip(labels, g.texts)):
                if lab not in rows:
                    continue
                if jp.get(lab) != t:
                    raise SystemExit(f'원문 불일치 {short}/{lab}: {t!r} != {jp.get(lab)!r}')
                ko = rows[lab]
                if ko is None:
                    if (short, lab) not in seen:
                        missing.append((short, lab))
                        seen.add((short, lab))
                    continue
                check_tags(lab, t, ko)
                g.texts[i] = ko
                if short != 'language':          # 언어 목록은 language 글꼴로만 그린다
                    need |= text_chars(ko)
                hit = True
            if hit:
                changes[p][(e['name'], e['hash'])] = g.build()
    if missing:
        print(f'미번역 {len(missing)}칸 (예: {missing[:3]})')
        if not partial:
            raise SystemExit('미번역 칸이 있다')
    return changes, need, need_eng


# ── 글꼴 ──
def bc3_g(gray):
    """H×W 농도 → BC3 블록 선형 바이트, 값은 G 채널(R·B=123, A=255) — 원본 페이지와 같은 꼴."""
    H, W = gray.shape
    blocks = gray.reshape(H // 4, 4, W // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16).astype(np.int32)
    hi = (blocks.max(1) * 63 + 127) // 255
    lo = (blocks.min(1) * 63 + 127) // 255
    same = hi == lo
    hi = np.where(same, np.minimum(63, lo + 1), hi)
    lo = np.where(same & (hi == lo), lo - 1, np.where(same, hi - 1, lo))
    g0 = (hi << 2) | (hi >> 4)
    g1 = (lo << 2) | (lo >> 4)
    pal = np.stack([g0, g1, (2 * g0 + g1) // 3, (g0 + 2 * g1) // 3], 1)          # N×4
    idx = np.abs(blocks[:, :, None] - pal[:, None, :]).argmin(2).astype(np.uint32)  # N×16
    bits = np.zeros(len(blocks), np.uint64)
    for k in range(16):
        bits |= idx[:, k].astype(np.uint64) << np.uint64(2 * k)
    out = np.zeros((len(blocks), 16), np.uint8)
    out[:, 0] = 255
    out[:, 1] = 255
    c0 = (15 << 11) | (hi << 5) | 15
    c1 = (15 << 11) | (lo << 5) | 15
    out[:, 8] = c0 & 0xFF
    out[:, 9] = c0 >> 8
    out[:, 10] = c1 & 0xFF
    out[:, 11] = c1 >> 8
    for k in range(4):
        out[:, 12 + k] = (bits >> np.uint64(8 * k)) & np.uint64(0xFF)
    return out.tobytes()


def pack(sizes, page_h=PAGE):
    pos, page, x, y, row = [], 0, 0, 0, 0
    for w, h in sizes:
        if x + w > PAGE:
            x, y, row = 0, y + row + GAP, 0
        if y + h > page_h:
            page, x, y, row = page + 1, 0, 0, 0
        pos.append((page, x, y))
        x += w + GAP
        row = max(row, h)
    return pos, (page + 1 if sizes else 0)


def render(font, ch):
    l, t, r, b = font.getbbox(ch, anchor='ls')
    adv = font.getlength(ch)
    if r <= l or b <= t:
        return None, 0, 0, adv
    w, h = r - l, b - t
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((-l, -t), ch, font=font, fill=255, anchor='ls')
    # 이 OTF 는 getbbox 가 잉크가 아니라 전진 상자를 돌려준다 → 실제 잉크로 자른다
    bb = im.getbbox()
    if bb is None:
        return None, 0, 0, adv
    im = im.crop(bb)
    return np.array(im), l + bb[0], t + bb[1], adv


def ink_bbox(font, ch):
    """글자의 실제 잉크 상자(기준선 원점)."""
    a, l, t, _ = render(font, ch)
    return l, t, l + a.shape[1], t + a.shape[0]


def jpn_metrics(fname):
    d, _, _, es = mtarc.parse(os.path.join(SRC, 'nativeNXx64', 'arc', 'system.arc'))
    e = next(e for e in es if e['name'] == FONT_PREFIX + fname + '_jpn')
    m = glyph_metrics(Gfd(mtarc.blob(d, e)))
    m['ref'] = list(m['ref'])
    m['ref'][7] = 0x0ffffa00
    return m


def glyph_metrics(g):
    """원본 한자(없으면 가나) 상자 중앙값으로 높이·세로 중심을 잡는다."""
    import statistics as st
    k = [r for c, r in g.chars.items() if 0x4E00 <= c < 0xA000 and r[0] > 0]
    if not k:
        k = [g.chars[ord(c)] for c in 'ロあ口日語' if ord(c) in g.chars and g.chars[ord(c)][0] > 0]
    h = st.median(r[1] for r in k)
    top = st.median(r[3] for r in k)
    return dict(top=top, h=h, lh=k[0][5], ref=k[0])


HANGUL_INK = 0.86      # 한글 잉크 높이 = 한자 상자 높이 × 이 값
HANGUL_GAP = 0.13      # 한글 글자 사이 = 잉크 높이 × 이 값


def build_font_data(fname, gb, need, font_cache, lang='jpn', page_h=PAGE):
    """원본 GFD 바이트 → (새 GFD 바이트, [(텍스처 이름, 바이트, 그림)], 글자 수, 페이지 수, 픽셀)"""
    wt, _ = FONTS[fname]
    g = Gfd(gb)
    chars = sorted(c for c in need if not c.isspace() and ord(c) not in g.chars)
    spaces = sorted(c for c in need if c.isspace() and c not in (chr(13), chr(10)) and ord(c) not in g.chars)
    if not chars and not spaces:
        return None, [], 0, 0, 0
    m = glyph_metrics(g) if lang != 'eng' else jpn_metrics(fname)
    ink = m['h'] * HANGUL_INK
    key = (wt, round(ink, 2))
    if key not in font_cache:
        probe = ImageFont.truetype(os.path.join(FONT_DIR, f'SCDream{wt}.otf'), 200)
        l, t, r, b = ink_bbox(probe, '한')
        px = max(8, round(200 * ink / (b - t)))
        font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, f'SCDream{wt}.otf'), px)
    font = font_cache[key]
    # 기준선: '한' 잉크 가운데를 한자 상자 가운데에 맞춘다
    l, t, r, b = ink_bbox(font, '한')
    base = m['top'] + m['h'] / 2 - (t + b) / 2
    gap = round(ink * HANGUL_GAP * 4) / 4
    for ch in spaces:
        sp = list(g.chars[0x20])
        g.chars[ord(ch)] = sp
    imgs, metas = [], []
    for ch in chars:
        a, l, t, adv = render(font, ch)
        if a is None:
            raise SystemExit(f'글꼴에 없는 글자: {ch!r} U+{ord(ch):04X}')
        imgs.append(a)
        if 0xAC00 <= ord(ch) <= 0xD7A3 or 0x3131 <= ord(ch) <= 0x318E:
            xo = gap / 2                          # 한글: 잉크 폭 + 간격(비례폭)
            adv = a.shape[1] + gap
        else:
            xo = l
            adv = round(adv * 4) / 4
        metas.append((xo, base + t, adv))
    pos, npages = pack([(a.shape[1], a.shape[0]) for a in imgs], page_h)
    canv = [np.zeros((page_h, PAGE), np.uint8) for _ in range(npages)]
    p0 = g.head[6]
    flag = m['ref'][7]
    for ch, a, (xo, yo, adv), (pg, x, y) in zip(chars, imgs, metas, pos):
        canv[pg][y:y + a.shape[0], x:x + a.shape[1]] = a
        g.chars[ord(ch)] = [float(a.shape[1]), float(a.shape[0]), float(xo), float(yo), float(adv), m['lh'],
                            (p0 + pg) | x << 8 | y << 20, flag]
    g.head[6] = p0 + npages
    texs = []
    hb = page_h // 4
    for k, c in enumerate(canv):
        lin = bc3_g(c)
        sw = deswizzle.swizzle(lin, PAGE // 4, hb, 16, fonttex.block_height(hb))
        texs.append((g.name + f'_{p0 + k:02d}_ID_HQ', sw, c))
    return g.build(), texs, len(chars), npages, font.size


TEX1024_HEAD = None


def tex1024_head():
    global TEX1024_HEAD
    if TEX1024_HEAD is None:
        d, _, _, es = mtarc.parse(os.path.join(SRC, 'nativeNXx64', 'arc', 'system.arc'))
        for e in es:
            if e['name'] == FONT_PREFIX + 'system_jpn_00_ID_HQ':
                TEX1024_HEAD = mtarc.blob(d, e)[:24]
    return TEX1024_HEAD


FIRST_PAGE = {}


def first_page(gname):
    """글꼴 첫 페이지 텍스처(같은 arc 에 없을 수 있어 전체에서 찾는다)."""
    if not FIRST_PAGE:
        for p in all_arcs():
            d, _, _, es = mtarc.parse(p)
            for x in es:
                if x['hash'] == TEX_HASH and x['name'].startswith(FONT_PREFIX) and x['name'].endswith('_00_ID_HQ'):
                    FIRST_PAGE.setdefault(x['name'][:-len('_00_ID_HQ')], mtarc.blob(d, x))
    return FIRST_PAGE[gname]


def build_fonts(need, report=False, need_eng=()):
    """글꼴 사본마다 결과가 같아야 한다(원본 사본이 다르면 각각 만든다)."""
    per_arc = defaultdict(lambda: ({}, []))
    cache, made = {}, {}
    sets = {'all': need, 'lang': set(LANG_NAME), 'eng': set(need_eng)}
    for p in all_arcs():
        d, _, _, es = mtarc.parse(p)
        names = {e['name'] for e in es}
        for e in es:
            if e['hash'] != GFD_HASH or not e['name'].startswith(FONT_PREFIX):
                continue
            fname, _, lang = e['name'][len(FONT_PREFIX):].rpartition('_')
            if fname not in FONTS or (lang != 'jpn' and fname != 'language' and not (lang == 'eng' and fname == 'system')):
                continue
            gb = mtarc.blob(d, e)
            t0 = first_page(Gfd(gb).name)
            W, H = fonttex.tex_dims(t0)
            if W != PAGE:
                raise SystemExit(f'페이지 폭이 {PAGE} 가 아니다: {e["name"]} {W}x{H}')
            k = (fname, lang, hash(gb), H)
            if k not in made:
                made[k] = build_font_data(fname, gb, sets['eng' if lang == 'eng' and fname == 'system' else FONTS[fname][1]], cache, lang, H) + (t0[:24],)
                r = made[k]
                if r[0] is not None:
                    print(f'  글꼴 {fname}_{lang}: 글자 {r[2]}개, 새 페이지 {r[3]}장 (픽셀 {r[4]})')
                    if report:
                        for tn, _, c in r[1]:
                            Image.fromarray(c).save(os.path.join(ROOT, '_work', 'shots', tn.split(BS)[-1] + '.png'))
            gnew, texs = made[k][0], made[k][1]
            if gnew is None:
                continue
            rep, add = per_arc[p]
            rep[(e['name'], GFD_HASH)] = gnew
            for tn, sw, _ in texs:
                if tn in names:
                    raise SystemExit(f'이미 있는 텍스처 이름: {tn}')
                prev = [a for a in add if a[0] == tn]
                if prev:
                    if prev[0][2] != made[k][5] + sw:
                        raise SystemExit(f'같은 이름 다른 텍스처: {tn}')
                    continue                      # 여러 글꼴 정의가 한 텍스처를 공유(language_*)
                add.append((tn, TEX_HASH, made[k][5] + sw))
    return per_arc


def main():
    partial = '--partial' in sys.argv
    report = '--report' in sys.argv
    if report:
        os.makedirs(os.path.join(ROOT, '_work', 'shots'), exist_ok=True)
    shutil.rmtree(OUT, ignore_errors=True)
    tr = load_tr()
    changes, need, need_eng = apply_gmd(tr, partial)
    print(f'GMD 바뀐 arc {len(changes)}개, 쓰인 글자 {len(need)}종 (한글 {sum(1 for c in need if 0xAC00 <= ord(c) <= 0xD7A3)})')
    fonts = build_fonts(need, report, need_eng)
    imgs = {}
    if os.path.exists(os.path.join(ROOT, 'tools', 'img_build.py')):
        import img_build
        imgs = img_build.build()
    targets = set(changes) | set(fonts) | set(imgs)
    for p in sorted(targets):
        rep = dict(changes.get(p, {}))
        add = []
        if p in fonts:
            rep.update(fonts[p][0])
            add += fonts[p][1]
        if p in imgs:
            rep.update(imgs[p])
        data = arcpack.rebuild(p, replace=rep, add=add)
        dst = os.path.join(OUT, os.path.relpath(p, SRC))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        # 되읽기: 바꾼 항목이 그대로 들어갔는지
        d2, _, _, es2 = mtarc.parse(dst)
        E2 = {(e['name'], e['hash']): e for e in es2}
        for k, v in rep.items():
            if mtarc.blob(d2, E2[k]) != v:
                raise SystemExit(f'되읽기 불일치 {p} {k}')
    print(f'출력 arc {len(targets)}개 -> {OUT}')
    if '--deploy' in sys.argv:
        deploy()


def deploy():
    if os.path.isdir(EDEN_MOD):
        shutil.rmtree(EDEN_MOD)
    shutil.copytree(OUT, os.path.join(EDEN_MOD, 'romfs'))
    print('배치:', EDEN_MOD)


if __name__ == '__main__':
    main()
