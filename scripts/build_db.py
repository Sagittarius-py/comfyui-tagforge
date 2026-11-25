"""Build data/tagforge.db from Danbooru (public API) and e621 (official daily db_export, static1.e621.net).

    python scripts/build_db.py                 # both sources
    python scripts/build_db.py --only e621 --min-count 20

Writes into a temporary file and swaps it in at the end, so a failed run never breaks
the database ComfyUI is using. Probe results from the old database are kept.
"""
import argparse
import csv
import gzip
import io
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tagforge_core import db  # noqa: E402

UA = "TagForge/0.1"  # Danbooru's Cloudflare answers 403 to UAs like "X (a; b)"


def get(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"  retry ({e})")
            time.sleep(3 * (attempt + 1))


def danbooru_pages(endpoint, params):
    page = 1
    while True:
        q = urllib.parse.urlencode({**params, "limit": 1000, "page": page})
        rows = json.loads(get(f"https://danbooru.donmai.us/{endpoint}.json?{q}"))
        if not rows:
            return
        yield rows
        page += 1
        time.sleep(0.5)  # be polite to the public API


def load_danbooru(con, min_count):
    n = 0
    for rows in danbooru_pages("tags", {"search[order]": "count", "search[post_count]": f">={min_count}",
                                        "search[is_deprecated]": "false"}):
        con.executemany("INSERT OR REPLACE INTO tags VALUES ('danbooru',?,?,?,?)",
                        [(r["name"], r["category"], r["post_count"], (r.get("created_at") or "")[:10] or None)
                         for r in rows])
        n += len(rows)
        print(f"  danbooru tags: {n}", end="\r")
    print()
    n = 0
    for rows in danbooru_pages("tag_aliases", {"search[status]": "active"}):
        con.executemany("INSERT OR REPLACE INTO aliases VALUES ('danbooru',?,?)",
                        [(r["antecedent_name"], r["consequent_name"]) for r in rows])
        n += len(rows)
        print(f"  danbooru aliases: {n}", end="\r")
    print()


def e621_rows(kind):
    url = f"https://static1.e621.net/data/db_export/{kind}.csv.gz"  # daily export, listed on e621.net/db_exports
    print(f"  downloading {url}")
    data = gzip.decompress(get(url))
    csv.field_size_limit(10 ** 7)
    return csv.DictReader(io.StringIO(data.decode("utf-8")))


def load_e621(con, min_count):
    con.executemany("INSERT OR REPLACE INTO tags VALUES ('e621',?,?,?,NULL)",
                    ((r["name"], int(r["category"]), int(r["post_count"])) for r in e621_rows("tags")
                     if int(r["post_count"]) >= min_count))
    con.executemany("INSERT OR REPLACE INTO aliases VALUES ('e621',?,?)",
                    ((r["antecedent_name"], r["consequent_name"]) for r in e621_rows("tag_aliases")
                     if r["status"] == "active"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["danbooru", "e621"])
    ap.add_argument("--min-count", type=int, default=10, help="skip tags with fewer posts")
    args = ap.parse_args()

    tmp = db.DB_PATH + ".new"
    if os.path.exists(tmp):
        os.remove(tmp)
    if os.path.exists(db.DB_PATH):
        shutil.copyfile(db.DB_PATH, tmp)  # keep the source we are not refreshing
    con = db.connect(tmp)
    for src, loader in (("danbooru", load_danbooru), ("e621", load_e621)):
        if args.only and args.only != src:
            continue
        print(f"{src}...")
        con.execute("DELETE FROM tags WHERE source=?", (src,))
        con.execute("DELETE FROM aliases WHERE source=?", (src,))
        loader(con, args.min_count)
        con.commit()
    print(db.TagDB(con).stats())
    con.close()
    try:
        os.replace(tmp, db.DB_PATH)
    except PermissionError:
        print(f"Baza jest otwarta przez ComfyUI. Zamknij ComfyUI i przenieś ręcznie:\n  {tmp} -> {db.DB_PATH}")
        return 1
    print(f"OK -> {db.DB_PATH} (zrestartuj ComfyUI albo odśwież stronę)")


if __name__ == "__main__":
    sys.exit(main())
