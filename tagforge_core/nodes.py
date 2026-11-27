import json
import random

from . import db, lists, translate as tr

MODELS = list(tr.MODELS)


def _tagdb():
    con = db.get()
    return db.TagDB(con) if con else None


class TagForgeTranslate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "text": ("STRING", {"multiline": True, "default": ""}),
            "model": (MODELS, {"default": "anima", "tooltip": "Target syntax: Anima (@artist) or Illustrious (plain artist name)."}),
            "tags_to": (["danbooru", "e621"], {"default": "danbooru", "tooltip": "Tag vocabulary of the output."}),
            "source": (["auto", "danbooru", "e621"], {"default": "auto", "tooltip": "Tag vocabulary of the input (auto = detect per tag)."}),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "report")
    FUNCTION = "run"
    CATEGORY = "TagForge"

    def run(self, text, model, tags_to, source):
        out, report = tr.translate(text, model, tags_to, source, _tagdb())
        if report["blocked"]:
            raise ValueError("TagForge: blocked minor-related content: " + ", ".join(sorted(set(report["blocked"]))))
        return out, tr.format_report(report)


class TagForgeArtists:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "artists": ("STRING", {"multiline": True, "default": "",
                                   "tooltip": "One artist per line or comma-separated. The 'Browse artists' button appends here."}),
            "model": (MODELS, {"default": "anima"}),
            "random_count": ("INT", {"default": 0, "min": 0, "max": 8,
                                     "tooltip": "0 = use the list. >0 = pick this many random artists from the 2000 most popular (older than the model's data cutoff)."}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF, "control_after_generate": True}),
            "random_from": (["top", "favorites"], {"default": "top",
                                                   "tooltip": "Random pool: the 2000 most popular artists, or your favorites. Blacklisted artists are never picked."}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    CATEGORY = "TagForge"

    def run(self, artists, model, random_count, seed, random_from="top"):
        picked = [tr.parse_chunk(a) for a in artists.replace("\n", ",").split(",") if a.strip()]
        picked = [(tr.canonical(p["inner"]), p["weight"]) for p in picked]
        if random_count:
            user = lists.load()
            banned = set(user["blacklist"])
            if random_from == "favorites":
                pool = [n for n in user["favorites"] if n not in banned]
                if not pool:
                    raise ValueError("TagForge: no favorite artists yet (star them in Browse artists…).")
            else:
                tagdb = _tagdb()
                if tagdb is None:
                    raise ValueError("TagForge: random artists need the tag database (scripts/build_db.py).")
                pool = [n for n, _, created in tagdb.artists("danbooru", limit=2000)
                        if tr.before_cutoff(model, created) and n not in banned]
                if not pool:
                    raise ValueError("TagForge: no artists in the database.")
            picked = [(n, None) for n in random.Random(seed).sample(pool, min(random_count, len(pool)))]
        out = [f"({tr.format_artist(n, model)}:{w})" if w else tr.format_artist(n, model) for n, w in picked]
        return (", ".join(out) + ("," if out else ""),)


RANDOM_TAB = "*"
RANDOM_TEXT_DEFAULT = json.dumps({"active": "background", "tabs": [
    {"name": "background", "text": "forest\nbeach\ncity street at night"},
    {"name": "weather", "text": "sunny\nrain\nsnow"},
]})


def text_options(data):
    """{tab name: options} from the tabs JSON, without blank lines, # comments and empty tabs."""
    tabs = {}
    for tab in json.loads(data)["tabs"]:
        lines = [l.strip() for l in tab["text"].splitlines() if l.strip() and not l.strip().startswith("#")]
        if lines:
            tabs[tab["name"]] = lines
    return tabs


class TagForgeRandomText:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "data": ("STRING", {"default": RANDOM_TEXT_DEFAULT}),  # edited through the tabs in the node
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF, "control_after_generate": True}),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "tab")
    FUNCTION = "run"
    CATEGORY = "TagForge"
    DESCRIPTION = "Picks one random option (one per line, # = comment) from the active tab. The 🎲 tab also picks the tab at random."

    def run(self, data, seed):
        tabs = text_options(data)
        active = json.loads(data)["active"]
        rng = random.Random(seed)
        if active == RANDOM_TAB:
            if not tabs:
                raise ValueError("TagForge: all tabs are empty - add options, one per line.")
            active = rng.choice(sorted(tabs))
        if active not in tabs:
            raise ValueError(f"TagForge: tab '{active}' has no options - add some, one per line.")
        return rng.choice(tabs[active]), active


NODE_CLASS_MAPPINGS = {"TagForgeTranslate": TagForgeTranslate, "TagForgeArtists": TagForgeArtists,
                       "TagForgeRandomText": TagForgeRandomText}
NODE_DISPLAY_NAME_MAPPINGS = {"TagForgeTranslate": "Tag Translator (TagForge)",
                              "TagForgeArtists": "Artist Picker (TagForge)",
                              "TagForgeRandomText": "Random Text (TagForge)"}
