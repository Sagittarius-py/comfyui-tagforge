"""Favorite / blacklisted artists and your own presets (data/user_lists.json), built-in presets (data/presets.json)."""
import json
import os
import threading

from . import translate as tr
from .db import DATA_DIR

USER_PATH = os.path.join(DATA_DIR, "user_lists.json")
PRESETS_PATH = os.path.join(DATA_DIR, "presets.json")
_lock = threading.Lock()


def load(path=None):
    try:
        with open(path or USER_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    return {"favorites": data.get("favorites", []), "blacklist": data.get("blacklist", []),
            "presets": data.get("presets", [])}


def builtin(path=None):
    with open(path or PRESETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _names(value):
    if not isinstance(value, list) or len(value) > 5000:
        raise ValueError("expected a list of up to 5000 artist names")
    return list(dict.fromkeys(tr.canonical(str(v))[:200] for v in value if str(v).strip()))


def _presets(value):
    if not isinstance(value, list) or len(value) > 500:
        raise ValueError("expected a list of up to 500 presets")
    out = []
    for p in value:
        if not isinstance(p, dict):
            raise ValueError("a preset must be an object with 'name' and 'artists'")
        name, artists = str(p.get("name", "")).strip()[:100], str(p.get("artists", "")).strip()[:2000]
        if name and artists:
            out.append({"name": name, "artists": artists})
    return out


def save(update, path=None):
    """Validate the keys present in `update`, merge them into the file and replace it atomically."""
    clean = {k: (_presets if k == "presets" else _names)(update[k])
             for k in ("favorites", "blacklist", "presets") if k in update}
    path = path or USER_PATH
    with _lock:
        data = {**load(path), **clean}
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    return data
