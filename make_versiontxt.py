import os
import re
from pathlib import Path

version = os.environ["GITHUB_REF_NAME"].removeprefix("v")

# Validate that this is a normal semantic version.
if not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", version):
    raise ValueError(f"Invalid version: {version!r}")

parts = tuple(int(x) for x in version.split("."))

if len(parts) > 4:
    raise ValueError(f"Windows file version has too many components: {version!r}")

# Windows file version resources require exactly four components.
filevers = parts + (0,) * (4 - len(parts))

Path("version.txt").write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={filevers},
    prodvers={filevers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('FileDescription', 'DBD Maps'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('ProductName', 'DBD Maps'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )