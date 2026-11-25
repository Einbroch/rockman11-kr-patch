"""MT Framework GMD (컬렉션 런처 문자열, 판 0x00010302) 읽기/쓰기.
머리 u32 9개: 마법 'GMD\\0', 판, 언어, ?, ?, 이름표 수, 본문 수, 이름표 문자열 크기, 본문 크기, 그다음 u32 이름 길이 + 이름 + NUL.
본문은 파일 맨 끝 [본문 크기] 바이트, NUL 로 끝나는 UTF-8 문자열 [본문 수] 개. 그 앞(이름표 항목·해시 표·이름표 문자열)은 그대로 둔다.
"""
import struct


class Gmd:
    def __init__(self, b):
        assert b[:4] == b'GMD\0', 'not GMD'
        self.head = list(struct.unpack_from('<9I', b, 0))
        self.n_labels, self.n_sections = self.head[5], self.head[6]
        self.sec_size = self.head[8]
        self.prefix = b[:len(b) - self.sec_size]
        body = b[len(b) - self.sec_size:]
        parts = body.split(b'\0')
        if parts and parts[-1] == b'':
            parts = parts[:-1]
        assert len(parts) == self.n_sections, (len(parts), self.n_sections)
        self.texts = [p.decode('utf-8') for p in parts]
        label_size = self.head[7]
        lab = b[len(b) - self.sec_size - label_size:len(b) - self.sec_size].split(b'\0')
        self.labels = [x.decode('utf-8', 'replace') for x in lab[:self.n_labels]]

    def build(self):
        body = b''.join(t.encode('utf-8') + b'\0' for t in self.texts)
        prefix = bytearray(self.prefix)
        struct.pack_into('<I', prefix, 8 * 4, len(body))
        return bytes(prefix) + body
