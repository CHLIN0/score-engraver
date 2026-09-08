"""Objective layout check of rendered pages: how full is each page, how crowded is each system.

    python page_balance.py render/ [--json out.json]

For every page-N.png: staves are found from their five equally spaced lines, staves are paired into
systems (grand staff) by gap, and the page fill is measured from the first system's top to the last
system's bottom (footer page numbers and titles do not count). Per system: ink density per unit
width and the gap to the next system. Flags: last page < 60 % of the fullest page's music extent, a stretched middle page (system gap > 1.3× the tightest page),
any other page < 50 %, a system much denser than the others (> 1.8× median), uneven inter-system
gaps (max/min > 1.6 on one page). Bars per system you know from your own \break plan.
Numbers, not opinions — the engraver decides the breaks. The page-extent numbers are reliable; the
system count and gaps are approximate on dense pages (beams and lyrics can look like staff lines) —
trust your eyes for those.
"""

import argparse, glob, json, pathlib
import numpy as np
from PIL import Image


def line_rows(gray, thresh=0.30):
    dark = (gray < 128).mean(axis=1)
    return np.where(dark >= thresh)[0]


def staves(gray):
    """Return [(top, bottom, spacing)] for every 5-line staff."""
    rows = line_rows(gray)
    if len(rows) == 0:
        return []
    lines = [rows[0]]
    for r in rows[1:]:
        if r - lines[-1] > 2:
            lines.append(r)
    out, i = [], 0
    while i + 4 < len(lines):
        seg = lines[i:i + 5]
        gaps = np.diff(seg)
        if gaps.min() >= 4 and gaps.std() <= 0.25 * gaps.mean():
            out.append((int(seg[0]), int(seg[-1]), float(gaps.mean())))
            i += 5
        else:
            i += 1
    return out


def systems_of(gray):
    st = staves(gray)
    if not st:
        return []
    if len(st) == 1:
        return [(st[0][0], st[0][1], 1)]
    gaps = np.array([st[i + 1][0] - st[i][1] for i in range(len(st) - 1)], dtype=float)
    heights = np.array([b - a for a, b, _ in st], dtype=float)
    # a grand staff's two staves sit closer than ~2 staff heights; between systems the gap is larger
    cut = 2.2 * float(np.median(heights))
    sys_, cur = [], [st[0]]
    for i, s in enumerate(st[1:]):
        if gaps[i] <= cut:
            cur.append(s)
        else:
            sys_.append(cur)
            cur = [s]
    sys_.append(cur)
    return [(g[0][0], g[-1][1], len(g)) for g in sys_]


def bars_in(gray, top, bottom):
    band = gray[top:bottom + 1]
    col = (band < 128).mean(axis=0)
    hits = np.where(col > 0.85)[0]         # a bar line spans the whole band
    if len(hits) == 0:
        return 0
    n, last = 0, -10
    for x in hits:
        if x - last > 6:
            n += 1
        last = x
    return max(0, n - 1)                   # left system brace/line and bar lines: bars = lines - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render_dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    pages = sorted(glob.glob(str(pathlib.Path(a.render_dir) / "page-*.png")),
                   key=lambda p: int(pathlib.Path(p).stem.split("-")[1]))
    report = {"pages": [], "flags": []}
    dens = []
    for p in pages:
        g = np.asarray(Image.open(p).convert("L"))
        h, w = g.shape
        systems = []
        for top, bot, nst in systems_of(g):
            band = g[max(0, top - 30): min(h, bot + 30)]
            cols = (band < 128).mean(axis=0)
            used = np.where(cols > 0.01)[0]
            width = float((used[-1] - used[0]) / w) if len(used) else 0.0
            density = float((band < 128).sum() / max(1, (used[-1] - used[0]))) if len(used) else 0.0
            systems.append({"top": int(top), "bottom": int(bot), "staves": nst,
                            "width_ratio": round(width, 3), "ink_per_px_width": round(density, 2)})
            dens.append(density)
        # ink past the right margin = a system that did not fit (LilyPond does not warn)
        colink = (g < 128).mean(axis=0)
        inked = np.where(colink > 0.002)[0]
        right_edge = float(inked[-1] / w) if len(inked) else 0.0
        gaps = [systems[i + 1]["top"] - systems[i]["bottom"] for i in range(len(systems) - 1)]
        extent = (systems[-1]["bottom"] - systems[0]["top"]) / h if systems else 0.0
        # inter-system gap: the large gaps (the small ones separate the two staves of one system when lyrics sit between them)
        big = [g for g in gaps if gaps and g > 1.5 * min(gaps)] or gaps
        system_gap = float(np.median(big)) if big else 0.0
        report["pages"].append({"page": pathlib.Path(p).name, "music_extent": round(extent, 3), "right_edge": round(right_edge, 3), "n_systems": len(systems),
                                "system_gap": round(system_gap), "gaps": gaps, "systems": systems})
    med = float(np.median(dens)) if dens else 0.0
    report["median_density"] = round(med, 2)
    fullest = max((pg["music_extent"] for pg in report["pages"]), default=0)
    # a stretched page: ragged-bottom = ##f spreads too few systems over the page, so it *looks* full (music_extent high)
    # while its systems sit much farther apart than on the neighbouring pages — one system too few on this page
    tight = [pg["system_gap"] for pg in report["pages"] if pg["system_gap"] > 0 and len(pg["gaps"]) >= 2]
    if len(tight) >= 2:
        ref = min(tight)
        for pg in report["pages"][:-1]:
            if pg["system_gap"] > 1.3 * ref and len(pg["gaps"]) >= 2:
                report["flags"].append(f"{pg['page']}: stretched — systems sit {pg['system_gap']} px apart vs {ref:.0f} px on the tightest page; this page holds one system too few (move a system up from the next page, or give the section start no new page)")
    for pg in report["pages"]:
        if pg["right_edge"] > 0.955:
            report["flags"].append(f"{pg['page']}: ink reaches {pg['right_edge']:.1%} of the page width — a system overflows the right margin (clipped bar); fewer bars on that system")
        for i, s in enumerate(pg["systems"], 1):
            if med and s["ink_per_px_width"] > 1.8 * med:
                report["flags"].append(f"{pg['page']} system {i}: much denser than the others ({s['ink_per_px_width']} vs median {med:.1f}) — check for crowding")
        if len(pg["gaps"]) >= 2 and min(pg["gaps"]) > 0 and max(pg["gaps"]) / min(pg["gaps"]) > 1.6:
            report["flags"].append(f"{pg['page']}: uneven system gaps {pg['gaps']}")
    if len(report["pages"]) > 1 and fullest:
        last = report["pages"][-1]
        # a lighter last page is normal (ragged-last-bottom); flag it only when it is clearly under-used — a stretched
        # middle page is the worse defect, so prefer 5+5+4 over 5+4+5
        if last["music_extent"] < 0.6 * fullest:
            report["flags"].append(f"{last['page']}: last page holds only {last['music_extent']:.0%} of the page height vs {fullest:.0%} on the fullest page — redistribute systems so pages end evenly")
        for pg in report["pages"][:-1]:
            if pg["music_extent"] < 0.5 * fullest:
                report["flags"].append(f"{pg['page']}: only {pg['music_extent']:.0%} used")
    out = json.dumps(report, indent=1)
    if a.json:
        open(a.json, "w").write(out)
    print(json.dumps({"pages": [(pg["page"], pg["music_extent"], pg["right_edge"], pg["n_systems"], pg["system_gap"]) for pg in report["pages"]],
                      "flags": report["flags"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
