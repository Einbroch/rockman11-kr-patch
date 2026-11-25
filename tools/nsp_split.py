"""NSP(PFS0) 를 안의 파일로 풀어 놓는다. 사용: python -I nsp_split.py <nsp> <outdir>"""
import os, sys
sys.path.insert(0, r'D:\Games\Kor Patch\CLude\Eastward\tools')
from nsptool import read_pfs0
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
with open(src, 'rb') as fh:
    for e in read_pfs0(fh):
        fh.seek(e['offset']); rem = e['size']
        with open(os.path.join(out, e['name']), 'wb') as o:
            while rem:
                b = fh.read(min(rem, 16 << 20)); o.write(b); rem -= len(b)
        print(e['size'], e['name'])
