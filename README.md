# File Compressor

A desktop app (Windows and Linux) that reduces the size of files. Drag files or folders
into the window, pick a quality level, and click **Compress**.

| File type | What happens |
| --- | --- |
| Images (JPG, PNG, WebP, GIF, TIFF, BMP) | Re-encoded and downscaled if very large; BMP becomes PNG |
| PDF | Embedded images re-encoded/downscaled, streams recompressed, unused objects removed |
| Office (DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB) | Embedded images shrunk, container repacked at maximum compression |
| Anything else | Packed into a ZIP or 7z archive |

Originals are never modified. Output is saved as `name_compressed.ext` (next to the original
or in a folder you choose), and only if it is actually smaller.

## Run from source

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m file_compressor
```

## Build a standalone executable

PyInstaller cannot cross-compile, so build on the target OS:

- Windows: `build_windows.bat` → `dist\FileCompressor.exe`
- Linux: `./build_linux.sh` → `dist/FileCompressor`

## Tests

```bash
pip install pytest
python -m pytest
```
