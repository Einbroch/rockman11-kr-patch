"""배포물 만들기 (게임 폴더에 둔다).

  Rockman11_KR_v<판>_atmosphere.zip : atmosphere/contents/0100B0C0086B0000/romfs/...   (스위치 실기)
  Rockman11_KR_v<판>_emulator.zip   : 0100B0C0086B0000/KoreanPatch/romfs/...          (Eden·yuzu 계열 load 폴더, Ryujinx mods)
  Rockman11_KR_v<판>_xdelta/        : 바뀐 arc 마다 원본→한글판 xdelta(옵션 없이 기본값) + 적용 안내
python tools/make_dist.py 1.0
"""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build', 'romfs')
SRC = os.path.join(ROOT, '_work', 'romfs')
TID = '0100B0C0086B0000'
XDELTA = os.path.join(os.path.dirname(ROOT), 'Rockman exe Leo', 'work', 'bin', 'xdelta3.exe')

README = """록맨 11 운명의 톱니바퀴!! (Nintendo Switch) 한글패치 v{ver}

[대상]
- 본편 0100B0C0086B0000 v0 + 업데이트 v1.0.2 (v131072) 기준입니다. 업데이트를 꼭 설치하세요.

[적용]
- 스위치 실기(Atmosphere): atmosphere.zip 을 SD 카드 루트에 풀어 덮어씁니다.
- Eden·yuzu 계열: 게임 우클릭 → 모드 폴더 열기(load/0100B0C0086B0000) 에 emulator.zip 안의 KoreanPatch 폴더를 넣습니다.
- Ryujinx: mods/contents/0100b0c0086b0000/ 아래에 KoreanPatch 폴더를 넣습니다.
- xdelta: 같은 이름의 원본 arc(RomFS nativeNXx64/arc/...)에 적용하면 한글판 arc 가 됩니다.

[게임 안 설정]
- 타이틀 → OPTIONS → 언어 설정 → 표시 언어를 「한국어」로 바꾸고 EXIT 하세요.
  (한국어는 일본어 칸에 들어 있습니다. 음성은 일본어·영어 중 자유롭게 고르세요.)

[범위]
- 이야기 장면·메뉴·옵션·아이템·무기 설명·상점·챌린지·업적·갤러리 등 게임 안 문장 전부
- 타이틀 로고 부제 「운명의 톱니바퀴!!」, 보스 소개 화면의 한글 이름, 시작 경고 화면(주의)
- 대화 장면 이름표(라이트 박사·와일리·록·롤·라이토트·블록맨)
- 언어 설정 전 부팅 문구(불러오는 중 등)는 영어 칸에도 한국어로 넣었습니다(본체 언어가 한국어면 영어 칸이 쓰임)
- 메뉴 영어 표기(GAME START 등)·스태프 롤은 일본판과 같이 원문 그대로입니다.
"""

APPLY_BAT = """@echo off
chcp 65001 >nul
rem 사용: 이 폴더에 원본 arc 를 같은 상대 경로(nativeNXx64\\arc\\...)로 두고 실행하면 out\\ 에 한글판이 만들어진다.
setlocal enabledelayedexpansion
for /r "%~dp0patch" %%F in (*.xdelta) do (
  set "rel=%%F"
  set "rel=!rel:%~dp0patch\\=!"
  set "rel=!rel:.xdelta=!"
  if not exist "%~dp0out\\!rel!\\.." mkdir "%~dp0out\\!rel!\\.."
  "%~dp0xdelta3.exe" -d -f -s "%~dp0!rel!" "%%F" "%~dp0out\\!rel!" || echo 실패: !rel!
)
echo 완료
pause
"""


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def files():
    out = []
    for dp, _, fn in os.walk(BUILD):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), BUILD))
    return sorted(out)


def make_zip(path, prefix, rels, ver):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        for r in rels:
            z.write(os.path.join(BUILD, r), os.path.join(prefix, r).replace(os.sep, '/'))
        z.writestr('README_한글패치.txt', README.format(ver=ver))


def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else '1.0'
    rels = files()
    base = os.path.join(ROOT, f'Rockman11_KR_v{ver}')
    make_zip(base + '_atmosphere.zip', f'atmosphere/contents/{TID}/romfs', rels, ver)
    make_zip(base + '_emulator.zip', f'{TID}/KoreanPatch/romfs', rels, ver)
    xd = base + '_xdelta'
    shutil.rmtree(xd, ignore_errors=True)
    sums = []
    for r in rels:
        src, dst = os.path.join(SRC, r), os.path.join(BUILD, r)
        out = os.path.join(xd, 'patch', r + '.xdelta')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([XDELTA, '-e', '-f', '-s', src, dst, out], check=True)
        # 되돌려 적용해 바이트 대조
        chk = out + '.chk'
        subprocess.run([XDELTA, '-d', '-f', '-s', src, out, chk], check=True)
        if sha1(chk) != sha1(dst):
            raise SystemExit(f'xdelta 되적용 불일치: {r}')
        os.remove(chk)
        sums.append(f'{sha1(src)}  {sha1(dst)}  {r}')
    shutil.copy(XDELTA, os.path.join(xd, 'xdelta3.exe'))
    open(os.path.join(xd, '적용.bat'), 'w', encoding='utf-8').write(APPLY_BAT)
    open(os.path.join(xd, 'SHA1_원본_한글판.txt'), 'w', encoding='utf-8').write('\n'.join(sums) + '\n')
    open(os.path.join(xd, 'README_한글패치.txt'), 'w', encoding='utf-8').write(README.format(ver=ver))
    for p in (base + '_atmosphere.zip', base + '_emulator.zip'):
        print(os.path.basename(p), os.path.getsize(p) // (1 << 20), 'MB')
    tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(xd) for f in fn)
    print(os.path.basename(xd), tot // (1 << 20), 'MB', len(rels), '개')


if __name__ == '__main__':
    main()
