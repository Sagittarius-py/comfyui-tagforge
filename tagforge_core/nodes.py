import random

from . import db, translate as tr

MODELS = list(tr.MODELS)


def _tagdb():
    con = db.get()
    return db.TagDB(con) if con else None


class TagForgeTranslate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "text": ("STRING", {"multiline": True, "default": ""}),
            "model": (MODELS, {"default": "anima", "tooltip": "Składnia docelowa: Anima (@artysta) albo Illustrious."}),
            "tags_to": (["danbooru", "e621"], {"default": "danbooru", "tooltip": "Zestaw tagów na wyjściu."}),
            "source": (["auto", "danbooru", "e621"], {"default": "auto", "tooltip": "Skąd pochodzą tagi wejściowe."}),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "report")
    FUNCTION = "run"
    CATEGORY = "TagForge"

    def run(self, text, model, tags_to, source):
        out, report = tr.translate(text, model, tags_to, source, _tagdb())
        if report["blocked"]:
            raise ValueError("TagForge: zablokowane treści z nieletnimi: " + ", ".join(sorted(set(report["blocked"]))))
        return out, tr.format_report(report)


class TagForgeArtists:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "artists": ("STRING", {"multiline": True, "default": "",
                                   "tooltip": "Jeden artysta w linii albo po przecinku. Przycisk 'Przeglądaj' dopisuje tutaj."}),
            "model": (MODELS, {"default": "anima"}),
            "random_count": ("INT", {"default": 0, "min": 0, "max": 8,
                                     "tooltip": "0 = użyj listy. >0 = losuj tylu z 2000 najpopularniejszych artystów (sprzed końca danych modelu)."}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF, "control_after_generate": True}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    CATEGORY = "TagForge"

    def run(self, artists, model, random_count, seed):
        names = [tr.canonical(tr.parse_chunk(a)["inner"]) for a in artists.replace("\n", ",").split(",") if a.strip()]
        if random_count:
            tagdb = _tagdb()
            if tagdb is None:
                raise ValueError("TagForge: losowanie wymaga bazy (scripts/build_db.py).")
            pool = [n for n, _, created in tagdb.artists("danbooru", limit=2000) if tr.before_cutoff(model, created)]
            if not pool:
                raise ValueError("TagForge: brak artystów w bazie.")
            names = random.Random(seed).sample(pool, min(random_count, len(pool)))
        return (", ".join(tr.format_artist(n, model) for n in names) + ("," if names else ""),)


NODE_CLASS_MAPPINGS = {"TagForgeTranslate": TagForgeTranslate, "TagForgeArtists": TagForgeArtists}
NODE_DISPLAY_NAME_MAPPINGS = {"TagForgeTranslate": "Tag Translator (TagForge)",
                              "TagForgeArtists": "Artist Picker (TagForge)"}
