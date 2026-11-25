"""압축 저장소(CompressedStorage) NCA 의 RomFS 추출기.

nstool 1.9.2 는 SDK 17+ 의 NCA 압축(fs 헤더 0x178 compression info)을 몰라
"Hash layer 4 failed" 로 끝난다. 계층 순서:

    raw NCA -> AES-CTR -> (업데이트면 BKTR indirect: base raw / patch AesCtrEx)
            -> CompressedStorage(LZ4) -> IVFC -> RomFS

업데이트의 indirect 가 base 를 가리킬 때는 base 의 *압축 해제 전* 복호화 바이트를 읽는다.
압축 표·엔트리 오프셋은 아래층의 IVFC 데이터층 시작 기준이다.

사용:
    python -I nca_romfs.py <outdir> <base.nca> <base.tik> [<update.nca> <update.tik>]
        [--list] [--only a,b] [--verify]
"""
import os
import struct
import sys

import lz4.block

sys.path.insert(0, r'D:\Games\Kor Patch\CLude\Eastward\tools')
from nsptool import Bktr, Nca, ivfc_data_range, load_keys, romfs_files  # noqa: E402

KEYS = r'D:\Games\Kor Patch\CLude\_tools\system\prod.keys'


def read_tik(path):
    blob = open(path, 'rb').read()
    sig = struct.unpack_from('<I', blob, 0)[0]
    base = {0x10000: 0x240, 0x10001: 0x140, 0x10002: 0x80,
            0x10003: 0x240, 0x10004: 0x140, 0x10005: 0x80}[sig]
    return blob[base + 0x160:base + 0x170].hex(), blob[base + 0x40:base + 0x50]


def open_nca(path, keys, titlekeys):
    fh = open(path, 'rb')
    return Nca(fh, 0, os.path.getsize(path), keys, titlekeys)


class Compressed:
    """bucket tree 압축 표: entry = (virt u64, phys u64, type u8, level s8, pad u16, psize u32)."""

    def __init__(self, lower_read, fs_header):
        off, size = struct.unpack_from('<QQ', fs_header, 0x178)
        if fs_header[0x188:0x18C] != b'BKTR':
            raise ValueError('compression BKTR 매직 없음')
        count = struct.unpack_from('<i', fs_header, 0x190)[0]
        raw = lower_read(off, size)
        nbuckets = struct.unpack_from('<I', raw, 4)[0]
        self.entries = []
        for b in range(nbuckets):
            base = 0x4000 * (b + 1)
            n = struct.unpack_from('<I', raw, base + 4)[0]
            for i in range(n):
                v, p, t, _lvl, _pad, ps = struct.unpack_from('<QQBbHI', raw, base + 0x10 + i * 0x18)
                self.entries.append((v, p, t, ps))
            end = struct.unpack_from('<Q', raw, base + 8)[0]
        if len(self.entries) != count:
            raise ValueError(f'압축 엔트리 수 불일치 {len(self.entries)} != {count}')
        self.end = end
        self.lower = lower_read
        self._cache = (None, None)

    def _find(self, value):
        lo, hi = 0, len(self.entries) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.entries[mid][0] <= value:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def _block(self, i):
        if self._cache[0] == i:
            return self._cache[1]
        v, p, t, ps = self.entries[i]
        vsize = (self.entries[i + 1][0] if i + 1 < len(self.entries) else self.end) - v
        if t == 0:
            data = None          # 비압축: 직접 범위 읽기
        elif t == 1:
            data = bytes(vsize)
        elif t == 3:
            data = lz4.block.decompress(self.lower(p, ps), uncompressed_size=vsize)
        else:
            raise NotImplementedError(f'압축 타입 {t}')
        self._cache = (i, data)
        return data

    def read(self, offset, length):
        out = bytearray()
        while length:
            i = self._find(offset)
            v, p, t, _ps = self.entries[i]
            nxt = self.entries[i + 1][0] if i + 1 < len(self.entries) else self.end
            take = min(length, nxt - offset)
            if t == 0:
                out += self.lower(p + (offset - v), take)
            else:
                blk = self._block(i)
                out += blk[offset - v:offset - v + take]
            offset += take
            length -= take
        return bytes(out)


def build_reader(base_path, base_tik, upd_path=None, upd_tik=None):
    keys = load_keys(KEYS)
    tks = dict([read_tik(base_tik)])
    if upd_tik:
        tks.update(dict([read_tik(upd_tik)]))
    bn = open_nca(base_path, keys, tks)
    bs = bn.romfs_section()
    if upd_path is None:
        fs = bs['fs_header']
        lower = lambda o, l: bn.read_section(bs, o, l)
    else:
        un = open_nca(upd_path, keys, tks)
        us = next(s for s in un.sections if s and s['enc_type'] == 4)
        fs = us['fs_header']
        lower = Bktr(un, us, bn, bs).read
    data_off, _ = ivfc_data_range(fs)
    if any(fs[0x178:0x188]):
        # 압축 표·엔트리 물리 오프셋은 IVFC 데이터층 시작 기준이고, 압축 해제한 가상 공간의
        # 0 이 곧 RomFS 헤더다 (실측: 표 off+size == 데이터층 크기).
        shifted = lambda o, l, _r=lower: _r(data_off + o, l)
        return Compressed(shifted, fs).read, 0
    return lower, data_off


def main():
    argv = sys.argv[1:]
    if '--only' in argv:
        i = argv.index('--only')
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith('--')]
    outdir, rest = args[0], args[1:]
    read, romfs_off = build_reader(*rest)
    listing = romfs_files(read, romfs_off)
    total = sum(f['size'] for f in listing)
    print(f'romfs off=0x{romfs_off:x} files={len(listing)} bytes={total}')
    if '--list' in sys.argv:
        for f in sorted(listing, key=lambda x: x['path']):
            print(f"{f['size']:12} {f['path']}")
        return
    only = None
    if '--only' in sys.argv:
        v = sys.argv[sys.argv.index('--only') + 1]
        if v.startswith('@'):
            v = open(v[1:], encoding='utf-8').read().strip()
        only = set(v.split(','))
    for f in listing:
        if only is not None and f['path'] not in only:
            continue
        dst = os.path.join(outdir, f['path'].replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as o:
            remaining, pos = f['size'], f['offset']
            while remaining:
                n = min(remaining, 8 << 20)
                o.write(read(pos, n))
                pos += n
                remaining -= n
    print('done')


if __name__ == '__main__':
    main()
