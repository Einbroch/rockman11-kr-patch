"""MT Framework TEX (8bpp atlas) header parser + PNG renderer."""
import struct, sys, os

def hdr(d):
    assert d[:4] == b"TEX\0"
    v1, v2 = struct.unpack_from("<II", d, 4)
    mip    = v2 & 0x3F
    width  = (v2 >> 6) & 0x1FFF
    height = (v2 >> 19) & 0x1FFF
    v3, v4 = struct.unpack_from("<II", d, 12)
    return dict(v1=v1, v2=v2, mip=mip, w=width, h=height, v3=v3, v4=v4,
                hdrlen=24, datalen=len(d) - 24)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        d = open(p, "rb").read()
        h = hdr(d)
        px = h["w"] * h["h"]
        print("%-14s w=%-5d h=%-5d mip=%d v1=0x%08x v3=0x%08x v4=0x%08x data=%d  data/(w*h)=%.4f  rows=data/w=%.1f"
              % (os.path.basename(p), h["w"], h["h"], h["mip"], h["v1"], h["v3"], h["v4"],
                 h["datalen"], h["datalen"] / px if px else 0,
                 h["datalen"] / h["w"] if h["w"] else 0))
