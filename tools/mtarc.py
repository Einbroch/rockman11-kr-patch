"""MT Framework ARC (magic 'ARC\0') unpacker/lister."""
import struct, zlib, sys, os

# MT Framework resource type hashes -> extension
EXT = {
    0x241f5deb: "tex",  0x2447d742: "gfd",  0x242bb29a: "gmd",
    0x22948394: "gui",  0x2749c8a8: "mrl",  0x1bcc4966: "srq",
    0x4c0db839: "sdl",  0x585831aa: "spkg", 0x2c4666d1: "smh",
    0x167dbbff: "stq",  0x4323d83a: "stex", 0x02358e1a: "spac",
    0x358012e8: "vib",  0x272b80ea: "prop", 0x0ecd7df4: "rtex",
    0x11c35522: "gr2",  0x3d97ad80: "amr",  0x0c4fcae4: "equ",
    0x2b40ae8f: "equr", 0x4E397417: "efl",  0x6d5ae854: "efs",
}

def parse(path, name_len=64):
    d = open(path, "rb").read()
    assert d[:4] == b"ARC\0", "not an ARC"
    ver, cnt = struct.unpack_from("<HH", d, 4)
    ent = 8
    esz = name_len + 16
    out = []
    for i in range(cnt):
        b = d[ent + i * esz : ent + (i + 1) * esz]
        if len(b) < esz:
            raise ValueError("entry table truncated at %d" % i)
        name = b[:name_len].split(b"\0")[0].decode("utf-8", "replace")
        ehash, csize, dsize_fl, off = struct.unpack_from("<IIII", b, name_len)
        out.append(dict(i=i, name=name, hash=ehash, ext=EXT.get(ehash, "%08x" % ehash),
                        csize=csize, dsize=dsize_fl & 0x1FFFFFFF,
                        flags=dsize_fl >> 29, off=off))
    return d, ver, cnt, out

def blob(d, e):
    raw = d[e["off"] : e["off"] + e["csize"]]
    if raw[:1] in (b"\x78",):          # zlib
        try:
            return zlib.decompress(raw)
        except zlib.error:
            pass
    return raw

if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    d, ver, cnt, ents = parse(path)
    if cmd == "list":
        print("version=%d count=%d filesize=%d" % (ver, cnt, len(d)))
        for e in ents:
            print("%4d  %-9s %9d %9d f%d @0x%08x  %s" %
                  (e["i"], e["ext"], e["csize"], e["dsize"], e["flags"], e["off"], e["name"]))
    elif cmd == "x":
        outdir = sys.argv[3]
        for e in ents:
            p = os.path.join(outdir, e["name"].replace("\\", os.sep) + "." + e["ext"])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            b = blob(d, e)
            open(p, "wb").write(b)
            if len(b) != e["dsize"]:
                print("[size mismatch] %s got=%d want=%d" % (e["name"], len(b), e["dsize"]))
        print("extracted %d files -> %s" % (cnt, outdir))
