"""MT Framework GFD 판 0x11007 (록맨 11) 읽기/쓰기.

머리 u32 10개: 'GFD\0', 판, 0, 3, 0, ?, 페이지 수[6], 글자 수[7], 0, 추가 실수 수[9]
실수 (4+머리[9])개, u32 이름 길이 + 이름 + NUL, 그다음 글자 36바이트 × 글자 수(코드 오름차순):
  u32 코드, f32 ×6 (가설: 폭, 높이, x오프셋, y오프셋, 전진폭, 줄높이), u32 위치(페이지|x<<8|y<<20), u32 기타
"""
import struct

REC = struct.Struct('<I6fII')


class Gfd:
    def __init__(self, b):
        assert b[:4] == b'GFD\0'
        self.head = list(struct.unpack_from('<10I', b, 0))
        nf = 4 + self.head[9]
        self.floats = list(struct.unpack_from('<%df' % nf, b, 0x28))
        no = 0x28 + 4 * nf
        nl = struct.unpack_from('<I', b, no)[0]
        he = no + 4 + nl + 1
        self.name = b[no + 4:no + 4 + nl].decode('utf-8')
        self.prefix = b[:he]
        n = self.head[7]
        if len(b) != he + REC.size * n:
            raise ValueError('GFD 길이 불일치 %d != %d' % (len(b), he + REC.size * n))
        self.chars = {}
        for i in range(n):
            r = list(REC.unpack_from(b, he + REC.size * i))
            self.chars[r[0]] = r[1:]

    def build(self):
        out = bytearray(self.prefix)
        struct.pack_into('<I', out, 6 * 4, self.head[6])
        struct.pack_into('<I', out, 7 * 4, len(self.chars))
        for code in sorted(self.chars):
            out += REC.pack(code, *self.chars[code])
        return bytes(out)

    @staticmethod
    def pos(r):
        v = r[6]
        return v & 0xFF, (v >> 8) & 0xFFF, (v >> 20) & 0xFFF
