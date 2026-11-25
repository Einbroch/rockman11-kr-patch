"""컬렉션 런처 글꼴 텍스처(MT TEX, BC7, Tegra 블록리니어) 읽기 도우미."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deswizzle
from PIL import Image


def block_height(h_blocks):
    gob_rows = (h_blocks + 7) // 8
    bh = 1
    while bh < gob_rows and bh < 16:
        bh *= 2
    return bh


def tex_dims(t):
    w = struct.unpack_from('<I', t, 8)[0]
    return (w >> 6) & 0x1FFF, (w >> 19) & 0x1FFF


def tex_alpha(t):
    W, H = tex_dims(t)
    hb = (H + 3) // 4
    lin, _ = deswizzle.deswizzle(t[24:], W // 4, hb, 16, block_height(hb))
    return Image.frombytes('RGBA', (W, H), lin, 'bcn', 7).split()[3]
