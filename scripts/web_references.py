"""Find reference material for a piece on the web, given its title/composer.

    python web_references.py --title "Nocturne Op. 9 No. 2" --composer "Chopin" --out DIR [--youtube 6] [--no-download]

Looks in four places and writes DIR/refs/refs.json plus downloaded files:
  Mutopia   (public-domain LilyPond editions) — searches make-table.cgi, DOWNLOADS .ly/.mid/-a4.pdf of
            the matching pieces into DIR/refs/mutopia/<piece>/ (they are CC/PD — allowed)
  IMSLP     (public-domain scans) — MediaWiki search; lists page titles + URLs only (open in a browser
            if you need to look; do not script downloads — IMSLP throttles and gates them)
  YouTube   (sheet-music / tutorial videos) — yt-dlp search, no download; lists title/channel/duration/URL,
            flags candidates whose title mentions sheet music / 樂譜 / 楽譜 / score / tutorial, so you can run
            source_dossier.py on the best one to get on-screen score frames
  Wikipedia (facts) — page summary for key, opus, form, tempo marking
Nothing here decides anything: the engraver reads refs.json, picks what matches the performance
(same key, same length, not an arrangement) and records adopted/rejected in engrave-report.json.
"""

import argparse, html, json, pathlib, re, subprocess, urllib.parse, urllib.request

UA = {"User-Agent": "score-engraver/2 (personal research; contact: local)"}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def mutopia_queries(title, composer):
    """Mutopia's search is a plain substring match on its table; try several phrasings."""
    qs = [title]
    cat = re.findall(r"(?:BWV|Op\.?|K\.?|KV|D\.?|Hob\.?|WoO)\s*\d+[a-z]?(?:\s*(?:No\.?|Nr\.?)\s*\d+)?", title, re.I)
    qs += cat
    words = [w for w in re.split(r"[\s,]+", title) if len(w) > 3 and not re.search(r"\d", w)]
    if composer:
        surname = composer.split()[-1]
        qs += [f"{surname} {w}" for w in words[:2]] + [surname]
    seen, out = set(), []
    for q in qs:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def mutopia_composer_rows(title, composer):
    """Fallback: Mutopia's composer tables (make-table.cgi?Composer=CODE). Codes come from browse.html;
    each piece in the table is a description block followed by a 'Download:' link group."""
    if not composer:
        return {}
    surname = composer.split()[-1].lower()
    try:
        browse = get("https://www.mutopiaproject.org/browse.html").decode("utf-8", "replace")
    except Exception:
        return {}
    codes = [c for c, txt in re.findall(r"""Composer=([A-Za-z]+)['"][^>]*>([^<]+)<""", browse) if surname in txt.lower()]
    nums = re.findall(r"\d+", title)
    words = [w.lower() for w in re.split(r"[\s,.]+", title) if len(w) > 3 and not re.search(r"\d", w)]
    ftp = r"""href=["'](https://www\.mutopiaproject\.org/ftp/[^"']+\.(?:ly|mid|pdf|zip))["']"""
    pieces = {}
    for code in dict.fromkeys(codes[:3]):
        try:
            page = get("https://www.mutopiaproject.org/cgibin/make-table.cgi?Composer=" + code, timeout=90).decode("utf-8", "replace")
        except Exception:
            continue
        blocks = page.split("Download:")
        desc = blocks[0]
        for b in blocks[1:]:
            text = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", desc))[-700:].lower()
            desc = b
            ok_nums = bool(nums) and all(re.search(r"\b" + n + r"\b", text) for n in nums)
            ok_words = any(w in text for w in words)
            if not (ok_nums or (ok_words and not nums)):
                continue
            for l in re.findall(ftp, b):
                slug = l.split("/")[-2]
                pieces.setdefault(slug, {"slug": slug, "files": [], "via": f"composer table {code}", "desc": text[-160:]})
                if l not in pieces[slug]["files"]:
                    pieces[slug]["files"].append(l)
    return pieces


def mutopia(title, out, composer="", download=True, max_pieces=12):
    result = {"queries": [], "pieces": []}
    pieces = {}
    for q in mutopia_queries(title, composer):
        url = "https://www.mutopiaproject.org/cgibin/make-table.cgi?searchingfor=" + urllib.parse.quote_plus(q)
        result["queries"].append(url)
        try:
            page = get(url).decode("utf-8", "replace")
        except Exception as e:
            result.setdefault("errors", []).append(f"{q}: {e}")
            continue
        links = re.findall(r'href="(https://www\.mutopiaproject\.org/ftp/[^"]+\.(?:ly|mid|pdf|zip))"', page)
        for l in links:
            slug = l.split("/")[-2]
            pieces.setdefault(slug, {"slug": slug, "files": []})
            if l not in pieces[slug]["files"]:
                pieces[slug]["files"].append(l)
        if len(pieces) >= max_pieces:
            break
    for slug, p in mutopia_composer_rows(title, composer).items():   # composer-table hits go first
        pieces.setdefault(slug, p)
        pieces[slug]["via"] = p.get("via")
    pieces = dict(sorted(pieces.items(), key=lambda kv: 0 if kv[1].get("via") else 1))
    for slug, p in list(pieces.items())[:max_pieces]:
        entry = {"slug": slug, "files": p["files"], "downloaded": [], "via": p.get("via", "title search")}
        if download:
            d = out / "mutopia" / slug
            d.mkdir(parents=True, exist_ok=True)
            for f in p["files"]:
                if f.endswith(".zip") or f.endswith("-let.pdf"):
                    continue
                dest = d / f.split("/")[-1]
                if not dest.exists():
                    try:
                        dest.write_bytes(get(f, timeout=60))
                    except Exception as e:
                        entry.setdefault("errors", []).append(f"{f}: {e}")
                        continue
                entry["downloaded"].append(str(dest))
            ly = next((x for x in entry["downloaded"] if x.endswith(".ly")), None)
            if ly:
                head = pathlib.Path(ly).read_text(errors="replace")[:4000]
                m = re.search(r'title\s*=\s*"([^"]+)"', head)
                c = re.search(r'composer\s*=\s*"([^"]+)"', head)
                k = re.search(r"\\key\s+([a-g](?:is|es|s)?)\s*\\(major|minor)", head)
                t = re.search(r"\\time\s+(\d+/\d+)", head)
                entry.update({"title": m.group(1) if m else None, "composer": c.group(1) if c else None,
                              "key": f"{k.group(1)} {k.group(2)}" if k else None, "time": t.group(1) if t else None})
        result["pieces"].append(entry)
    return result


def imslp(query, limit=6):
    url = (
        "https://imslp.org/api.php?action=query&list=search&format=json&srlimit=%d&srsearch=%s"
        % (limit, urllib.parse.quote_plus(query))
    )
    try:
        d = json.loads(get(url))
    except Exception as e:
        return {"error": str(e), "url": url, "pages": []}
    pages = []
    for s in d.get("query", {}).get("search", []):
        t = s["title"]
        pages.append(
            {
                "title": t,
                "url": "https://imslp.org/wiki/"
                + urllib.parse.quote(t.replace(" ", "_")),
                "snippet": re.sub("<[^>]+>", "", html.unescape(s.get("snippet", "")))[
                    :160
                ],
            }
        )
    return {"url": url, "pages": pages}


def youtube(query, n=6):
    try:
        out = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--dump-single-json",
                "--no-warnings",
                f"ytsearch{n}:{query}",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        ).stdout
        d = json.loads(out)
    except Exception as e:
        return {"error": str(e), "query": query, "videos": []}
    vids = []
    for e in d.get("entries", []):
        title = e.get("title") or ""
        flag = bool(
            re.search(
                r"sheet|score|樂譜|楽譜|琴譜|tutorial|synthesia|with score|附譜",
                title,
                re.I,
            )
        )
        vids.append(
            {
                "title": title,
                "channel": e.get("channel") or e.get("uploader"),
                "duration_s": e.get("duration"),
                "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                "shows_score_likely": flag,
            }
        )
    return {"query": query, "videos": vids}


def wikipedia(query):
    try:
        s = json.loads(
            get(
                "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=6&srsearch="
                + urllib.parse.quote_plus(query)
            )
        )
        hits = s.get("query", {}).get("search", [])
        if not hits:
            return {"query": query}
        nums = re.findall(r"\d+", query)
        title = next((h["title"] for h in hits if all(n in h["title"] for n in nums)), hits[0]["title"])
        summ = json.loads(
            get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(title.replace(" ", "_"))
            )
        )
        return {
            "query": query,
            "title": title,
            "url": summ.get("content_urls", {}).get("desktop", {}).get("page"),
            "extract": (summ.get("extract") or "")[:900],
        }
    except Exception as e:
        return {"query": query, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--composer", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--youtube", type=int, default=6)
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    out = pathlib.Path(a.out) / "refs"
    out.mkdir(parents=True, exist_ok=True)
    q = f"{a.title} {a.composer}".strip()
    refs = {
        "query": q,
        "mutopia": mutopia(a.title, out, composer=a.composer, download=not a.no_download),
        "imslp": imslp(q),
        "youtube_sheet_music": youtube(q + " sheet music", a.youtube),
        "youtube_performance": youtube(q + " piano", 4),
        "wikipedia": wikipedia(q),
    }
    json.dump(refs, open(out / "refs.json", "w"), ensure_ascii=False, indent=1)
    mp = refs["mutopia"].get("pieces", [])
    print(
        json.dumps(
            {
                "mutopia_pieces": [
                    (
                        p.get("title") or p["slug"],
                        p.get("key"),
                        p.get("time"),
                        len(p.get("downloaded", [])),
                    )
                    for p in mp
                ],
                "imslp_pages": [p["title"] for p in refs["imslp"].get("pages", [])][:4],
                "youtube_with_score": [
                    v["title"]
                    for v in refs["youtube_sheet_music"].get("videos", [])
                    if v["shows_score_likely"]
                ][:4],
                "wikipedia": refs["wikipedia"].get("title"),
                "refs_json": str(out / "refs.json"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
