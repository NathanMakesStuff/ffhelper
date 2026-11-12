# PyInstaller recipe for the bundled app. Run packaging/build.ps1 instead of calling this directly.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root / "src")],
    datas=[
        (str(root / "config.example.toml"), "."),
        (str(root / "mechanics"), "mechanics"),
        *collect_data_files("rapidocr"),  # OCR models and their YAML configs
    ],
    hiddenimports=["rapidocr.main"],  # rapidocr imports this lazily
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ffhelper", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="FFHelper", upx=False)
