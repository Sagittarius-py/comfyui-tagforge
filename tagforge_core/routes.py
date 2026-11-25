"""HTTP routes for the frontend (autocomplete, tag check, artist list)."""
from urllib.parse import quote

from aiohttp import web

from . import translate as tr
from .nodes import _tagdb


def _sources(value):
    return ("danbooru", "e621") if value == "both" else (value if value in ("danbooru", "e621") else "danbooru",)


def register(routes):
    @routes.get("/tagforge/status")
    async def status(request):
        tagdb = _tagdb()
        return web.json_response({"db": bool(tagdb), "stats": tagdb.stats() if tagdb else None})

    @routes.get("/tagforge/search")
    async def search(request):
        tagdb = _tagdb()
        q = tr.canonical(request.query.get("q", "")).lstrip("@")
        if not tagdb or len(q) < 2:
            return web.json_response([])
        limit = min(int(request.query.get("limit", 15)), 50)
        rows = [r for r in tagdb.search(q, _sources(request.query.get("source", "danbooru")), limit)
                if r["name"] not in tr.BLOCKED_TAGS]
        return web.json_response(rows)

    @routes.post("/tagforge/check")
    async def check(request):
        body = await request.json()
        source = body.get("source", "danbooru")
        _, report = tr.translate(str(body.get("text", ""))[:20000], body.get("model", "anima"),
                                 source if source in ("danbooru", "e621") else "danbooru", "auto", _tagdb())
        return web.json_response({k: sorted(set(report[k])) for k in ("unknown", "blocked")})

    @routes.get("/tagforge/artists")
    async def artists(request):
        tagdb = _tagdb()
        if not tagdb:
            return web.json_response({"db": False, "items": []})
        model = request.query.get("model", "anima")
        model = model if model in tr.MODELS else "anima"
        offset = max(int(request.query.get("offset", 0)), 0)
        rows = tagdb.artists("danbooru", request.query.get("q", ""), limit=100, offset=offset)
        items = [{"name": name, "text": tr.format_artist(name, model), "count": count,
                  "url": "https://danbooru.donmai.us/artists/show_or_new?name=" + quote(name)}
                 for name, count, _ in rows]
        return web.json_response({"db": True, "items": items, "next": offset + len(rows)})
