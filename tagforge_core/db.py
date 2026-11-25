"""SQLite store for booru tags and aliases. Stdlib only."""
import os
import sqlite3
import threading

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "tagforge.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tags (
    source TEXT NOT NULL,          -- 'danbooru' | 'e621'
    name TEXT NOT NULL,            -- canonical booru form, underscores
    category INTEGER NOT NULL,
    count INTEGER NOT NULL,
    created_at TEXT,               -- ISO date, may be NULL (e621 export has none)
    PRIMARY KEY (source, name)
);
CREATE TABLE IF NOT EXISTS aliases (
    source TEXT NOT NULL,
    antecedent TEXT NOT NULL,
    consequent TEXT NOT NULL,
    PRIMARY KEY (source, antecedent)
);
CREATE INDEX IF NOT EXISTS tags_cat_count ON tags (source, category, count DESC);
"""

# Artist category is 1 on both Danbooru and e621.
ARTIST = 1
CATEGORY_NAMES = {
    "danbooru": {0: "general", 1: "artist", 3: "copyright", 4: "character", 5: "meta"},
    "e621": {0: "general", 1: "artist", 3: "copyright", 4: "character", 5: "species",
             6: "invalid", 7: "meta", 8: "lore"},
}

_local = threading.local()


def connect(path=None):
    """New connection (used by build scripts and tests)."""
    path = path or DB_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def get(path=None):
    """Per-thread cached read connection, or None when the database was never built."""
    path = path or DB_PATH
    if not os.path.exists(path):
        return None
    con = getattr(_local, "con", None)
    if con is None or getattr(_local, "path", None) != path:
        con = connect(path)
        _local.con, _local.path = con, path
    return con


class TagDB:
    """Read-only lookups. Works on an explicit connection so tests can use :memory:."""

    def __init__(self, con):
        self.con = con

    def lookup(self, source, name):
        """(name, category, count) after alias resolution, or None."""
        row = self.con.execute(
            "SELECT name, category, count FROM tags WHERE source=? AND name=?", (source, name)).fetchone()
        if row:
            return row
        alias = self.con.execute(
            "SELECT consequent FROM aliases WHERE source=? AND antecedent=?", (source, name)).fetchone()
        if alias:
            return self.con.execute(
                "SELECT name, category, count FROM tags WHERE source=? AND name=?", (source, alias[0])).fetchone() \
                or (alias[0], 0, 0)
        return None

    def search(self, prefix, sources=("danbooru",), limit=20):
        """Prefix search over tags and alias antecedents, best counts first."""
        hi = prefix + "￿"
        out, seen = [], set()
        for src in sources:
            rows = self.con.execute(
                "SELECT name, category, count, NULL FROM tags WHERE source=? AND name>=? AND name<? "
                "ORDER BY count DESC LIMIT ?", (src, prefix, hi, limit)).fetchall()
            rows += self.con.execute(
                "SELECT t.name, t.category, t.count, a.antecedent FROM aliases a "
                "JOIN tags t ON t.source=a.source AND t.name=a.consequent "
                "WHERE a.source=? AND a.antecedent>=? AND a.antecedent<? ORDER BY t.count DESC LIMIT ?",
                (src, prefix, hi, limit)).fetchall()
            for name, cat, count, alias in rows:
                if (src, name) in seen:
                    continue
                seen.add((src, name))
                out.append({"name": name, "category": cat, "count": count, "source": src,
                            "category_name": CATEGORY_NAMES[src].get(cat, str(cat)), "alias": alias})
        out.sort(key=lambda r: -r["count"])
        return out[:limit]

    def artists(self, source, query="", limit=60, offset=0):
        q = query.strip().lower().replace(" ", "_").lstrip("@")
        sql = ("SELECT name, count, created_at FROM tags WHERE source=? AND category=? "
               + ("AND name LIKE ? " if q else "") + "ORDER BY count DESC LIMIT ? OFFSET ?")
        args = [source, ARTIST] + ([f"%{q}%"] if q else []) + [limit, offset]
        return self.con.execute(sql, args).fetchall()

    def stats(self):
        return {src: {"tags": self.con.execute("SELECT COUNT(*) FROM tags WHERE source=?", (src,)).fetchone()[0],
                      "aliases": self.con.execute("SELECT COUNT(*) FROM aliases WHERE source=?", (src,)).fetchone()[0]}
                for src in ("danbooru", "e621")}
