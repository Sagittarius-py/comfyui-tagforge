"""Self-check: python tests/test_core.py  (no ComfyUI, no network, in-memory DB)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tagforge_core import db, translate as tr  # noqa: E402


def fixture():
    con = db.connect(":memory:")
    con.executemany("INSERT INTO tags VALUES (?,?,?,?,?)", [
        ("danbooru", "1boy", 0, 1000000, "2005-01-01"), ("danbooru", "furry", 0, 200000, "2006-01-01"),
        ("danbooru", "espeon", 4, 9000, "2007-01-01"), ("danbooru", "pink_fur", 0, 3000, "2010-01-01"),
        ("danbooru", "closed_eyes", 0, 900000, "2005-01-01"), ("danbooru", "quasarcake", 1, 400, "2016-01-01"),
        ("danbooru", "new_artist", 1, 400, "2026-01-01"), ("danbooru", "hatsune_miku", 4, 100000, "2007-01-01"),
        ("danbooru", "kid_icarus", 3, 5000, "2010-01-01"), ("danbooru", "pokemon_(creature)", 3, 90000, "2008-01-01"),
        ("e621", "anthro", 0, 3000000, None), ("e621", "espeon", 5, 20000, None), ("e621", "eyes_closed", 0, 500000, None),
        ("e621", "quasarcake_(artist)", 1, 900, None), ("e621", "male", 0, 4000000, None), ("e621", "young", 0, 1, None),
    ])
    con.executemany("INSERT INTO tags VALUES (?,?,?,?,?)", [("e621", "glistening_fur", 0, 5000, None)])
    con.executemany("INSERT INTO aliases VALUES (?,?,?)", [("e621", "shiny_fur", "glistening_fur"),
                                                          ("danbooru", "miku", "hatsune_miku"),
                                                          ("danbooru", "lolicon", "loli")])
    return db.TagDB(con)


def run():
    t = fixture()

    # e621 -> danbooru, Anima syntax
    out, rep = tr.translate("anthro, male, eyes_closed, quasarcake_(artist), (espeon:1.4), pink_body", "anima", tagdb=t)
    assert out == "furry, 1boy, closed eyes, @quasarcake, (espeon:1.4), pink fur,", out
    assert "Anima needs higher weights" in tr.format_report(rep)

    # e621-only alias with no danbooru equivalent keeps the user's word
    out, rep = tr.translate("shiny fur", "anima", tagdb=t)
    assert out == "shiny fur,", out
    assert rep["no_equivalent"] == ["shiny_fur"], rep

    # danbooru -> e621
    out, _ = tr.translate("1boy, furry, closed eyes", "illustrious", tags_to="e621", tagdb=t)
    assert out == "male, anthro, eyes closed,", out

    # artist detection from category, aliases, escaping, score tags, natural language kept, lines kept
    out, rep = tr.translate("score_9, quasarcake, miku, pokemon_(creature)\nA cozy bedroom at night with warm light.",
                            "anima", tagdb=t)
    assert out == "score_9, @quasarcake, hatsune miku, pokemon \\(creature\\),\nA cozy bedroom at night with warm light.,", out
    out, _ = tr.translate("@quasarcake, hatsune miku", "illustrious", tagdb=t)
    assert out == "quasarcake, hatsune miku,", out
    out, rep = tr.translate("embedding:lazypos, (embedding:lazyneg:0.8), miku", "illustrious", tagdb=t)
    assert out == "embedding:lazypos, (embedding:lazyneg:0.8), hatsune miku,", out
    assert rep["unknown"] == [], rep

    # unknown tags and duplicates
    out, rep = tr.translate("purpla short hair, espeon, espeon", "anima", tagdb=t)
    assert out == "purpla short hair, espeon,", out
    assert rep["unknown"] == ["purpla_short_hair"], rep
    _, rep = tr.translate("masterpiece, best quality, newest, year 2024, explicit, score_7_up, addmicrodetails", "anima", tagdb=t)
    assert rep["unknown"] == [], rep

    # hard block: tags, aliases, words, ages; never via settings
    for bad in ("loli", "lolicon", "cub", "young", "a small child sitting on the bed in the room.", "15 years old",
                "(shota:0.5)"):
        _, rep = tr.translate(f"1boy, {bad}", "anima", tagdb=t)
        assert rep["blocked"], bad
    for ok in ("1boy", "petite", "25 years old", "adult woman"):
        _, rep = tr.translate(ok, "anima", tagdb=t)
        assert not rep["blocked"], ok

    # works without database
    out, rep = tr.translate("@some artist, long hair", "anima", tagdb=None)
    assert out == "@some artist, long hair,", out
    assert rep["notes"]

    # random artist pool: only tags older than the model's data cutoff
    assert tr.before_cutoff("anima", "2016-01-01") and tr.before_cutoff("anima", None)
    assert not tr.before_cutoff("anima", "2026-01-01")
    assert not tr.before_cutoff("illustrious", "2024-05-01")

    # search: prefix + aliases, best count first
    names = [r["name"] for r in t.search("hats")] + [r["name"] for r in t.search("mik")]
    assert names == ["hatsune_miku", "hatsune_miku"], names
    print("OK")


if __name__ == "__main__":
    run()
