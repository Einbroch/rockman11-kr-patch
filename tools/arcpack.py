"""MT Framework ARC 다시 쓰기: 바꾼 항목만 zlib 로 새로 압축하고 나머지는 원래 압축 바이트 그대로, 항목 추가 가능.
엔트리 80바이트(name[64] + 타입 해시 + 압축 크기 + 크기|플래그<<29 + 위치). 크기 칸은 실제 크기(이 컬렉션 런처 관례)."""
import struct
import zlib
import mtarc

NAME_LEN = 64


def rebuild(path, replace=None, add=None, remove=None):
    """replace: {항목 이름: 새 원본 바이트}, add: [(이름, 타입 해시, 원본 바이트)] → 새 arc 바이트"""
    replace = dict(replace or {})
    remove = set(remove or ())
    add = list(add or [])
    d, ver, cnt, ents = mtarc.parse(path)
    names = {e['name'] for e in ents}
    keys = {(e['name'], e['hash']) for e in ents}
    for n in replace:
        if (n not in keys) if isinstance(n, tuple) else (n not in names):
            raise KeyError(n)
    items = []   # (이름, 해시, 압축 바이트, 크기|플래그)
    for e in sorted(ents, key=lambda x: x['i']):
        k = (e['name'], e['hash'])
        if k in remove:
            remove.discard(k)
            continue
        if k in replace or e['name'] in replace:
            raw = replace.pop(k) if k in replace else replace.pop(e['name'])
            items.append((e['name'], e['hash'], zlib.compress(raw, 9), len(raw) | (e['flags'] << 29)))
        else:
            items.append((e['name'], e['hash'], d[e['off']:e['off'] + e['csize']], e['dsize'] | (e['flags'] << 29)))
    if remove:
        raise KeyError(f'없는 항목 제거: {remove}')
    flags = ents[0]['flags'] if ents else 2
    for name, h, raw in add:
        if name in names:
            raise KeyError(f'이미 있는 항목: {name}')
        items.append((name, h, zlib.compress(raw, 9), len(raw) | (flags << 29)))
    n = len(items)
    first_orig = min(e['off'] for e in ents)
    tbl_end = 8 + n * (NAME_LEN + 16)
    start = max(first_orig, (tbl_end + 0x7FFF) & ~0x7FFF) if tbl_end > first_orig else first_orig
    out = bytearray(start)
    out[0:8] = struct.pack('<4sHH', b'ARC\0', ver, n)
    cur = start
    offs = []
    for name, h, comp, sz in items:
        offs.append(cur)
        cur += len(comp)
    for k, (name, h, comp, sz) in enumerate(items):
        base = 8 + k * (NAME_LEN + 16)
        nb = name.encode('utf-8')
        assert len(nb) < NAME_LEN
        out[base:base + NAME_LEN] = nb.ljust(NAME_LEN, b'\0')
        struct.pack_into('<IIII', out, base + NAME_LEN, h, len(comp), sz, offs[k])
    for name, h, comp, sz in items:
        out += comp
    return bytes(out)
