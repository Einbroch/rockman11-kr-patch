"""정적 폭 검사: 번역 줄 폭이 같은 칸 원문(일본어) 최장 줄보다 넓으면 보고한다.
폭 = 빌드된 system_jpn 글꼴의 전진폭 합(태그 제외). 원문 최장 줄 대비 비율 > LIMIT 를 실패로.
  python tools/width_check.py [LIMIT]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build   # noqa: E402
import mtarc   # noqa: E402
from gfd11 import Gfd  # noqa: E402

TAG = re.compile(r'<[^<>]*>')
B = chr(92)


def load_font():
    p = os.path.join(build.OUT, 'nativeNXx64', 'arc', 'system.arc')
    d, _, _, es = mtarc.parse(p)
    e = next(e for e in es if e['name'] == build.FONT_PREFIX + 'system_jpn')
    return Gfd(mtarc.blob(d, e))


def width(g, s):
    w = 0.0
    for ch in TAG.sub('', s):
        r = g.chars.get(ord(ch))
        w += r[4] if r else 40
    return w


def main():
    limit = float(sys.argv[1]) if len(sys.argv) > 1 else 1.10
    g = load_font()
    tr = build.load_tr()
    bad = []
    for name, (rows, jp) in tr.items():
        if name in ('credit', 'language'):
            continue
        for lab, ko in rows.items():
            if not ko:
                continue
            jw = max(width(g, l) for l in jp[lab].split('\r\n'))
            for l in ko.split('\r\n'):
                kw = width(g, l)
                if jw > 0 and kw > jw * limit and kw - jw > 30:
                    bad.append((round(kw / jw, 2), name, lab, l))
    bad.sort(reverse=True)
    for b in bad:
        print(*b)
    print(f'넓은 줄 {len(bad)}개 (기준 {limit})')


if __name__ == '__main__':
    main()
