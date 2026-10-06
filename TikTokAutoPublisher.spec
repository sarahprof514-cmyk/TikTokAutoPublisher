# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
datas=[]; binaries=[]; hiddenimports=[]
for pkg in ("playwright","watchdog","PySide6"):
    d,b,h=collect_all(pkg); datas+=d; binaries+=b; hiddenimports+=h
a=Analysis(["main.py"],pathex=["."],binaries=binaries,datas=datas,hiddenimports=hiddenimports)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name="TikTokAutoPublisher",console=False,upx=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name="TikTokAutoPublisher")
