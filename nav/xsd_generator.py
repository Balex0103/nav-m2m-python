from __future__ import annotations

import os
from pathlib import Path


def list_xsd_files(vdr_dir: str) -> list[str]:
    if not os.path.isdir(vdr_dir):
        return []
    return sorted(str(Path(vdr_dir) / name) for name in os.listdir(vdr_dir) if name.lower().endswith('.xsd'))


def primary_xsd(vdr_dir: str) -> str | None:
    files = list_xsd_files(vdr_dir)
    if not files:
        return None
    preferred = ['eArData.xsd', 'formData.xsd', 'common.xsd']
    lowered = {os.path.basename(f).lower(): f for f in files}
    for name in preferred:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return files[0]
