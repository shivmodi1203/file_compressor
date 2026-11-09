"""Builds File Compressor for the current OS and packages it for distribution.

Output goes to release/:
  Windows: FileCompressor-<version>-windows-setup.exe (needs Inno Setup 6.3+)
           FileCompressor-<version>-windows-portable.zip
  Linux:   FileCompressor-<version>-x86_64.AppImage (needs appimagetool)
           FileCompressor-<version>-linux-x86_64.tar.gz
"""
from __future__ import annotations

import importlib.metadata as metadata
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from file_compressor import APP_NAME, HOMEPAGE, PUBLISHER, __version__  # noqa: E402

EXE_NAME = "FileCompressor"
DESKTOP_ID = "file-compressor"
RESOURCES = ROOT / "file_compressor" / "resources"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
APP_DIR = DIST / EXE_NAME
IS_WINDOWS = sys.platform == "win32"

RUNTIME_REQUIREMENTS = ["PySide6-Essentials", "Pillow", "pikepdf", "py7zr"]
# These packages do not ship their licence text in their metadata.
EXTRA_LICENSE_TEXTS = {
    "pyside6-essentials": ["LGPL-3.0.txt", "GPL-3.0.txt"],
    "shiboken6": ["LGPL-3.0.txt", "GPL-3.0.txt"],
}
LICENSE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)


def run(cmd: list) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


# ----- PyInstaller ----------------------------------------------------------


def write_windows_version_file() -> Path:
    numbers = tuple(int(n) for n in re.findall(r"\d+", __version__)[:3]) + (0,)
    numbers = (numbers + (0, 0, 0))[:4]
    strings = {
        "CompanyName": PUBLISHER,
        "FileDescription": APP_NAME,
        "FileVersion": __version__,
        "InternalName": EXE_NAME,
        "LegalCopyright": f"Copyright (c) {PUBLISHER}",
        "OriginalFilename": f"{EXE_NAME}.exe",
        "ProductName": APP_NAME,
        "ProductVersion": __version__,
    }
    entries = ",\n          ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())
    path = BUILD / "version_info.txt"
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
          {entries}])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
    )
    return path


def build_app() -> None:
    if APP_DIR.is_file():
        APP_DIR.unlink()
    shutil.rmtree(APP_DIR, ignore_errors=True)
    BUILD.mkdir(exist_ok=True)
    sep = ";" if IS_WINDOWS else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        # A folder build (not --onefile) keeps the Qt libraries replaceable, as the LGPL requires.
        "--onedir",
        "--name", EXE_NAME,
        "--icon", RESOURCES / ("icon.ico" if IS_WINDOWS else "icon.png"),
        "--add-data", f"{RESOURCES}{sep}file_compressor/resources",
        "--distpath", DIST,
        "--workpath", BUILD,
        "--specpath", BUILD,
    ]
    if IS_WINDOWS:
        cmd += ["--version-file", write_windows_version_file()]
    run(cmd + [ROOT / "file_compressor" / "__main__.py"])


# ----- Licences -------------------------------------------------------------


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_distributions() -> dict[str, metadata.Distribution]:
    found: dict[str, metadata.Distribution] = {}

    def walk(name: str) -> None:
        key = _normalize(name)
        if key in found:
            return
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            return
        found[key] = dist
        for requirement in map(Requirement, dist.requires or []):
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                walk(requirement.name)

    for name in RUNTIME_REQUIREMENTS:
        walk(name)
    return dict(sorted(found.items()))


def _license_name(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    license_field = (meta.get("License") or "").strip()
    if license_field and "\n" not in license_field and len(license_field) < 80:
        return license_field
    classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classifiers) or "See licence files"


def write_licenses(target: Path) -> None:
    shutil.copy2(ROOT / "LICENSE", target / "LICENSE.txt")
    licenses_dir = target / "licenses"
    shutil.rmtree(licenses_dir, ignore_errors=True)
    licenses_dir.mkdir()

    rows = []
    for key, dist in runtime_distributions().items():
        name, version = dist.metadata["Name"], dist.version
        package_dir = licenses_dir / f"{name}-{version}"
        package_dir.mkdir()
        for file in dist.files or []:
            if LICENSE_FILE.search(file.name):
                shutil.copy2(file.locate(), package_dir / file.name)
        for text in EXTRA_LICENSE_TEXTS.get(key, []):
            shutil.copy2(ROOT / "licenses" / text, package_dir / text)
        rows.append(f"| {name} | {version} | {_license_name(dist)} |")

    python_license = Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"
    if not python_license.exists():
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        (licenses_dir / f"Python-{sys.version.split()[0]}").mkdir()
        shutil.copy2(python_license, licenses_dir / f"Python-{sys.version.split()[0]}" / "LICENSE.txt")
        rows.insert(0, f"| Python | {sys.version.split()[0]} | PSF-2.0 |")

    (target / "THIRD_PARTY_NOTICES.md").write_text(
        f"""# Third-party software in {APP_NAME} {__version__}

{APP_NAME} is distributed under the MIT licence (see LICENSE.txt). It includes the
open-source components listed below. Their full licence texts are in the `licenses` folder.

Qt / PySide6, shiboken6 and py7zr (with its compression helpers) are used under the
GNU LGPL. These libraries are shipped as separate files inside this application's folder
and may be replaced with compatible versions of your choice. The complete source code of
{APP_NAME} is available at {HOMEPAGE}.

| Component | Version | Licence |
| --- | --- | --- |
{chr(10).join(rows)}
""",
        encoding="utf-8",
    )


# ----- Packaging ------------------------------------------------------------


def find_iscc() -> Path | None:
    on_path = shutil.which("iscc") or shutil.which("ISCC")
    if on_path:
        return Path(on_path)
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and (Path(base) / "Inno Setup 6" / "ISCC.exe").exists():
            return Path(base) / "Inno Setup 6" / "ISCC.exe"
    return None


def package_windows() -> None:
    shutil.make_archive(str(RELEASE / f"{EXE_NAME}-{__version__}-windows-portable"), "zip", DIST, EXE_NAME)
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup not found: skipping the installer (https://jrsoftware.org/isdl.php).")
        return
    run([
        iscc,
        f"/DAppVersion={__version__}",
        f"/DAppPublisher={PUBLISHER}",
        f"/DAppURL={HOMEPAGE}",
        f"/DAppSourceDir={APP_DIR}",
        f"/DOutputDir={RELEASE}",
        ROOT / "installer" / "FileCompressor.iss",
    ])


def package_linux() -> None:
    shutil.make_archive(str(RELEASE / f"{EXE_NAME}-{__version__}-linux-x86_64"), "gztar", DIST, EXE_NAME)
    appimagetool = os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool")
    if not appimagetool:
        print("appimagetool not found: skipping the AppImage (set APPIMAGETOOL to its path).")
        return

    appdir = BUILD / f"{EXE_NAME}.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(APP_DIR, appdir / "usr" / "bin")
    shutil.copy2(RESOURCES / "icon.png", appdir / f"{DESKTOP_ID}.png")
    (appdir / f"{DESKTOP_ID}.desktop").write_text(
        f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Comment=Reduce the size of images, PDFs, documents and other files
Exec={EXE_NAME} %F
Icon={DESKTOP_ID}
Categories=Utility;Archiving;Compression;
Terminal=false
""",
        encoding="utf-8",
    )
    apprun = appdir / "AppRun"
    apprun.write_text(
        f'#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/bin/{EXE_NAME}" "$@"\n',
        encoding="utf-8",
    )
    apprun.chmod(0o755)

    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    output = RELEASE / f"{EXE_NAME}-{__version__}-x86_64.AppImage"
    cmd = [appimagetool]
    # Without a local runtime file, appimagetool downloads one from GitHub on every build.
    if os.environ.get("APPIMAGE_RUNTIME"):
        cmd += ["--runtime-file", os.environ["APPIMAGE_RUNTIME"]]
    cmd += [str(appdir), str(output)]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    build_app()
    write_licenses(APP_DIR)
    shutil.rmtree(RELEASE, ignore_errors=True)
    RELEASE.mkdir()
    if IS_WINDOWS:
        package_windows()
    else:
        package_linux()
    print("\nRelease files:")
    for path in sorted(RELEASE.iterdir()):
        print(f"  {path.relative_to(ROOT)}  ({path.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
