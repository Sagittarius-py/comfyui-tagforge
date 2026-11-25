"""Prompt parsing, Danbooru <-> e621 translation, per-model syntax, hard minor-content block."""
import csv
import os
import re

from .db import ARTIST

# Model facts. Anima: circlestone-labs/Anima model card (Sept 2025 anime cutoff, '@artist',
# spaces not underscores except score_*, weights need ~2 like '(chibi:2)').
# Illustrious: trained on Danbooru2023 -> cutoff end of 2023 (card states no exact date).
MODELS = {
    "anima": {"cutoff": "2025-09-30"},
    "illustrious": {"cutoff": "2023-12-31"},
}

# Quality / meta / safety tags the models were trained with but boorus do not have
# (Anima card + common Illustrious/NoobAI ones). Never reported as unknown.
MODEL_TAGS = {
    "masterpiece", "best_quality", "amazing_quality", "great_quality", "high_quality", "good_quality",
    "normal_quality", "average_quality", "low_quality", "bad_quality", "worst_quality", "very_aesthetic",
    "aesthetic", "displeasing", "very_displeasing", "newest", "recent", "mid", "early", "old", "safe",
    "sensitive", "nsfw", "explicit", "questionable", "general", "ye-pop", "deviantart", "highres", "absurdres",
}
YEAR = re.compile(r"^year_\d{4}$")
_CUSTOM_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "custom_tags.txt")
_custom = (None, set())


def custom_tags():
    """Your own known tags (LoRA triggers etc.), one per line in data/custom_tags.txt; reloaded on change."""
    global _custom
    try:
        mtime = os.path.getmtime(_CUSTOM_PATH)
    except OSError:
        return set()
    if _custom[0] != mtime:
        with open(_CUSTOM_PATH, encoding="utf-8") as f:
            _custom = (mtime, {canonical(l) for l in f if l.strip() and not l.startswith("#")})
    return _custom[1]


def is_model_tag(name):
    return name in MODEL_TAGS or bool(SCORE.match(name) or YEAR.match(name)) or name in custom_tags()


# ---- hard block: never configurable -------------------------------------------------------
BLOCKED_TAGS = {
    "loli", "lolicon", "shota", "shotacon", "toddler", "child", "children", "male_child",
    "female_child", "kid", "kids", "infant", "baby", "young", "cub", "underage", "preteen",
    "aged_down", "child_on_child", "elementary_school_student", "kindergarten_uniform",
}
BLOCKED_WORDS = re.compile(
    r"\b(loli|lolicon|shota|shotacon|cub|cubs|child|children|kid|kids|toddler|infant|preteen|underage)\b", re.I)
AGE = re.compile(r"\b(\d{1,2})\s*[- ]?\s*(?:years?[- ]old|yo|y/o)\b", re.I)


def blocked_reason(canonical, raw_text):
    if canonical in BLOCKED_TAGS:
        return canonical
    m = BLOCKED_WORDS.search(raw_text)
    if m:
        return m.group(1).lower()
    for m in AGE.finditer(raw_text):
        if int(m.group(1)) < 18:
            return m.group(0)
    return None


# ---- manual e621 -> danbooru table (data/mapping_e621_danbooru.csv) -----------------------
_MAP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                         "mapping_e621_danbooru.csv")
_MAP = None


def manual_map():
    global _MAP
    if _MAP is None:
        e2d, d2e = {}, {}
        with open(_MAP_PATH, encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row or row[0].startswith("#"):
                    continue
                e, d = row[0].strip(), row[1].strip()
                e2d.setdefault(e, d)
                d2e.setdefault(d, e)
        _MAP = {"e621": e2d, "danbooru": d2e}
    return _MAP


# ---- parsing ------------------------------------------------------------------------------
WEIGHT = re.compile(r"^\((.+):\s*([0-9]*\.?[0-9]+)\)$", re.S)
SCORE = re.compile(r"^score_\d+(_up)?$")


def canonical(tag):
    return re.sub(r"\s+", "_", tag.strip().lower())


def display(name):
    """Booru name -> prompt text: spaces, escaped parentheses (ComfyUI parses '(' as weight)."""
    text = name if SCORE.match(name) else name.replace("_", " ")
    return text.replace("(", r"\(").replace(")", r"\)")


def parse_chunk(chunk):
    """-> dict(raw, inner, weight, artist, natural) for one comma-separated piece."""
    raw = chunk.strip()
    inner, weight = raw, None
    m = WEIGHT.match(raw)
    if m:
        inner, weight = m.group(1).strip(), m.group(2)
    elif raw.startswith("(") and raw.endswith(")") and not raw.startswith("\\"):
        inner, weight = raw[1:-1].strip(), "1.1"
    inner = inner.replace(r"\(", "(").replace(r"\)", ")")
    artist = False
    for prefix in ("@", "artist:", "by "):
        if inner.lower().startswith(prefix):
            inner, artist = inner[len(prefix):].strip(), True
            break
    natural = inner.endswith(".") or len(inner.split()) >= 6
    return {"raw": raw, "inner": inner, "weight": weight, "artist": artist, "natural": natural}


def format_artist(name, model):
    text = display(name)
    return "@" + text if model == "anima" else text


# ---- translation --------------------------------------------------------------------------
def _to_target(tagdb, name, src, dst, report):
    """Map canonical tag from src set to dst set. Returns (name, category or None)."""
    original = name
    found = tagdb.lookup(src, name) if tagdb else None
    if found:
        name = found[0]
    if src == dst:
        return name, (found[1] if found else None)
    manual = manual_map()[src].get(name)
    if manual is not None:
        report["translated"].append(f"{name} -> {manual or '(dropped)'}")
        return manual, None
    candidates = list(dict.fromkeys([name, original]))
    if name.endswith("_(artist)"):
        candidates.append(name[: -len("_(artist)")])
    for cand in candidates:
        hit = tagdb.lookup(dst, cand) if tagdb else None
        if hit:
            if hit[0] != name:
                report["translated"].append(f"{name} -> {hit[0]}")
            return hit[0], hit[1]
    # no equivalent: keep what the user wrote, not the source site's alias (shiny_fur, not glistening_fur)
    report["no_equivalent"].append(original)
    return original, (found[1] if found else None)


def translate(text, model="anima", tags_to="danbooru", source="auto", tagdb=None):
    """-> (prompt, report dict). Lines are kept, chunks re-joined with ', '."""
    report = {"blocked": [], "translated": [], "no_equivalent": [], "unknown": [], "artists": [], "notes": []}
    if tagdb is None:
        report["notes"].append("No tag database (run scripts/build_db.py) - only syntax and blocking are applied.")
    seen, out_lines = set(), []
    for line in text.splitlines():
        out = []
        for chunk in line.split(","):
            if not chunk.strip():
                continue
            p = parse_chunk(chunk)
            name = canonical(p["inner"])
            reason = blocked_reason(name, p["inner"])
            if p["natural"]:
                if reason:
                    report["blocked"].append(reason)
                    continue
                out.append(p["raw"])
                continue
            src = source
            if src == "auto":
                src = "danbooru"
                in_e621 = name in manual_map()["e621"] or (tagdb and tagdb.lookup("e621", name))
                if in_e621 and not (tagdb and tagdb.lookup("danbooru", name)):
                    src = "e621"
            model_tag = is_model_tag(name)
            name, cat = (name, None) if model_tag else _to_target(tagdb, name, src, tags_to, report)
            if not name:
                continue
            reason = reason or blocked_reason(name, name.replace("_", " "))
            if reason:
                report["blocked"].append(reason)
                continue
            if tagdb and cat is None and not model_tag and not tagdb.lookup(tags_to, name):
                report["unknown"].append(name)
            is_artist = p["artist"] or cat == ARTIST
            text_out = format_artist(name, model) if is_artist else display(name)
            if is_artist:
                report["artists"].append(text_out)
            if p["weight"]:
                text_out = f"({text_out}:{p['weight']})"
            if text_out in seen:
                continue
            seen.add(text_out)
            out.append(text_out)
        if out:
            out_lines.append(", ".join(out) + ",")
    if model == "illustrious" and any(SCORE.match(canonical(c)) for c in re.split(r"[,\n]", text)):
        report["notes"].append("score_* are Pony/Anima tags - Illustrious does not know them.")
    if model == "anima" and re.search(r":\s*1\.[0-4]\)", "\n".join(out_lines)):
        report["notes"].append("Anima needs higher weights than SDXL (model card example: (chibi:2)).")
    return "\n".join(out_lines), report


def format_report(report):
    labels = [("blocked", "BLOCKED"), ("translated", "Translated"), ("no_equivalent", "No equivalent"),
              ("unknown", "Unknown tags"), ("artists", "Artists"), ("notes", "Notes")]
    lines = [f"{label}: {', '.join(dict.fromkeys(report[key]))}" for key, label in labels if report[key]]
    return "\n".join(lines) or "OK"


def before_cutoff(model, created_at):
    """Tag existed before the model's training data ended (artists newer than that are unknown to it)."""
    return created_at is None or created_at[:10] <= MODELS[model]["cutoff"]
