"""록맨 11 TEX 읽기/쓰기 도우미 (스위치, Tegra 블록리니어).

머리 24바이트: 'TEX\\0', u32, u32(밉 6비트|폭 13비트<<6|높이 13비트<<19), u32(바이트 0=?, 1=형식, ...), ...
형식: 0x2a = BC3(알파 있는 DXT5) 등. 밉 단계는 차례로 이어진다(단계마다 따로 스위즐).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deswizzle  # noqa: E402
from PIL import Image  # noqa: E402

# 형식 → (블록 바이트, 블록 크기, PIL 디코더 이름, 디코더 인수)
FMT = {
    0x2a: (16, 4, 'bcn', 3),     # BC3
    0x30: (16, 4, 'bcn', 7),     # BC7 (추정)
    0x13: (8, 4, 'bcn', 1),      # BC1
    0x17: (8, 4, 'bcn', 1),
    0x19: (16, 4, 'bcn', 7),     # BC7
    0x1f: (16, 4, 'bcn', 7),
    0x07: (4, 1, 'raw', 'RGBA'),
}


def info(t):
    v = struct.unpack_from('<I', t, 8)[0]
    mips = v & 0x3F
    w, h = (v >> 6) & 0x1FFF, (v >> 19) & 0x1FFF
    fmt = t[0x0D]
    return dict(w=w, h=h, mips=mips, fmt=fmt)


def block_height(h_blocks):
    gob_rows = (h_blocks + 7) // 8
    bh = 1
    while bh < gob_rows and bh < 16:
        bh *= 2
    return bh


def level_size(w, h, fmt):
    bb, bs = FMT[fmt][0], FMT[fmt][1]
    wb, hb = max(1, (w + bs - 1) // bs), max(1, (h + bs - 1) // bs)
    bh = block_height(hb)
    gw = (wb * bb + 63) // 64
    gh = (hb + 8 * bh - 1) // (8 * bh)
    return gw * gh * 512 * bh, wb, hb, bh


def decode(t, level=0):
    i = info(t)
    fmt = i['fmt']
    off = 24
    w, h = i['w'], i['h']
    for _ in range(level):
        size, *_ = level_size(w, h, fmt)
        off += size
        w, h = max(1, w // 2), max(1, h // 2)
    size, wb, hb, bh = level_size(w, h, fmt)
    bb, bs, dec, arg = FMT[fmt]
    lin, _ = deswizzle.deswizzle(t[off:off + size], wb, hb, bb, bh)
    if dec == 'raw':
        return Image.frombytes('RGBA', (w, h), lin[:w * h * 4])
    return Image.frombytes('RGBA', (wb * bs, hb * bs), lin, dec, arg).crop((0, 0, w, h))


if __name__ == '__main__':
    import mtarc
    p, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
    d, _, _, es = mtarc.parse(p)
    for e in es:
        if e['name'].endswith(name) and e['ext'] == 'tex':
            t = mtarc.blob(d, e)
            print(e['name'], info(t), t[:24].hex())
            decode(t).save(out)
            break
