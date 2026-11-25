"""Tegra X1 block-linear -> linear deswizzle."""
import sys, os
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mttex import hdr

def deswizzle(data, width, height, bpp, block_height):
    row_bytes = width * bpp
    gobs_x = (row_bytes + 63) // 64
    gob_rows = (height + 7) // 8
    gob_rows_al = ((gob_rows + block_height - 1) // block_height) * block_height
    out = bytearray(row_bytes * height)
    for y in range(height):
        gy, iy = divmod(y, 8)
        blk, gy_in = divmod(gy, block_height)
        base_blk = blk * gobs_x * block_height * 512
        yb = ((iy // 2) * 64) + ((iy % 2) * 16)
        for xb0 in range(0, row_bytes, 16):
            gx, ix = divmod(xb0, 64)
            src = (base_blk + (gx * block_height + gy_in) * 512
                   + (ix // 32) * 256 + yb + ((ix % 32) // 16) * 32)
            dst = y * row_bytes + xb0
            out[dst:dst + 16] = data[src:src + 16]
    return bytes(out), gob_rows_al

def load(path, bpp=4, bh=16):
    d = open(path, "rb").read()
    h = hdr(d)
    lin, _ = deswizzle(d[24:], h["w"], h["h"], bpp, bh)
    return Image.frombytes("RGBA", (h["w"], h["h"]), lin), h

if __name__ == "__main__":
    out = sys.argv[-1]
    os.makedirs(out, exist_ok=True)
    for p in sys.argv[1:-1]:
        img, h = load(p)
        b = os.path.basename(p).replace(".tex", "")
        a = img.getchannel("A")
        a.save("%s/%s_alpha.png" % (out, b))
        img.convert("RGB").save("%s/%s_rgb.png" % (out, b))
        print("%-14s %dx%d -> %s_alpha.png / _rgb.png" % (b, h["w"], h["h"], b))

def swizzle(linear, width, height, bpp, block_height):
    """inverse of deswizzle()"""
    row_bytes = width * bpp
    gobs_x = (row_bytes + 63) // 64
    gob_rows = (height + 7) // 8
    gob_rows_al = ((gob_rows + block_height - 1) // block_height) * block_height
    out = bytearray(gobs_x * gob_rows_al * 512)
    for y in range(height):
        gy, iy = divmod(y, 8)
        blk, gy_in = divmod(gy, block_height)
        base_blk = blk * gobs_x * block_height * 512
        yb = ((iy // 2) * 64) + ((iy % 2) * 16)
        for xb0 in range(0, row_bytes, 16):
            gx, ix = divmod(xb0, 64)
            dst = (base_blk + (gx * block_height + gy_in) * 512
                   + (ix // 32) * 256 + yb + ((ix % 32) // 16) * 32)
            src = y * row_bytes + xb0
            out[dst:dst + 16] = linear[src:src + 16]
    return bytes(out)
