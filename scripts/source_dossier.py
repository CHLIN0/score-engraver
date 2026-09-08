"""Build a source dossier for a piece: metadata, audio for transcription, and every frame of the
video that shows sheet music (deduplicated, cropped, laid out on contact sheets for the engraver to
look at).

    python source_dossier.py <URL | video.mp4 | audio.wav> --out DIR [--every 2] [--max-keep 120]

Outputs in DIR/dossier/:
  meta.json        title, uploader, description, tags, duration (from yt-dlp) or file facts
  audio.wav        mono 44.1 kHz audio for the AMT model
  frames/          one JPEG every --every seconds (1280 px wide)
  crops/           the sheet-music band of each kept frame (staff lines detected)
  sheets/          contact sheets (6 crops per page, timestamps printed) — read these
  dossier.json     everything above as data, plus which frames were kept and why

Sheet-music detection is a plain heuristic: rows whose dark-ish pixels (< 150) span ≥ 30 % of the width are
"line rows"; a frame with ≥ 8 line rows arranged in ≥ 2 groups of near-equal spacing has staves.
No OMR is attempted — the crops are for the engraver's eyes.
"""

import argparse, json, pathlib, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


def fetch_meta(url):
    out = run(
        ["yt-dlp", "--dump-single-json", "--no-warnings", "--skip-download", url]
    ).stdout
    d = json.loads(out)
    keys = (
        "id",
        "title",
        "uploader",
        "channel",
        "description",
        "tags",
        "duration",
        "upload_date",
        "webpage_url",
        "view_count",
        "width",
        "height",
        "fps",
        "chapters",
    )
    return {k: d.get(k) for k in keys}


def download(url, dest):
    run(
        [
            "yt-dlp",
            "--no-warnings",
            "-q",
            "-f",
            "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
            "--merge-output-format",
            "mp4",
            "-o",
            str(dest),
            url,
        ]
    )


def line_rows(gray, thresh=0.3):
    dark = gray < 150
    frac = dark.mean(axis=1)
    return np.where(frac >= thresh)[0]


def staff_groups(rows, max_gap=40):
    """Split line rows into vertical clusters and keep only staff-like ones: 4–6 lines with
    near-equal spacing (a keyboard edge or a table border is one or two lines, not a staff)."""
    if len(rows) == 0:
        return []
    groups, cur = [], [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= max_gap:
            cur.append(r)
        else:
            groups.append(cur)
            cur = [r]
    groups.append(cur)
    out = []
    for g in groups:
        lines = [g[0]]
        for r in g[1:]:
            if r - lines[-1] > 2:
                lines.append(r)
        if 4 <= len(lines) <= 7:
            gaps = np.diff(lines)
            if gaps.mean() >= 4 and gaps.std() <= 0.3 * gaps.mean():
                out.append(lines)
    return out


def has_sheet_music(gray):
    rows = line_rows(gray)
    groups = staff_groups(rows)
    return len(groups) >= 1 and sum(len(g) for g in groups) >= 8, groups


def dhash(img, size=8):
    g = img.convert("L").resize((size + 1, size))
    a = np.asarray(g, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def hamming(a, b):
    return int(np.count_nonzero(a != b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--max-keep", type=int, default=120)
    ap.add_argument(
        "--min-diff",
        type=int,
        default=6,
        help="dHash Hamming distance to keep a new crop",
    )
    a = ap.parse_args()
    out = pathlib.Path(a.out) / "dossier"
    for sub in ("frames", "crops", "sheets"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    src = a.source
    dossier = {"source": src, "every_s": a.every}
    if src.startswith("http"):
        meta = fetch_meta(src)
        video = out / "video.mp4"
        if not video.exists():
            download(src, video)
        dossier["meta"] = meta
        dossier["video"] = str(video)
    else:
        p = pathlib.Path(src)
        dossier["meta"] = {"title": p.stem, "file": str(p), "size": p.stat().st_size}
        video = p if p.suffix.lower() in (".mp4", ".mkv", ".mov", ".webm") else None
        dossier["video"] = str(video) if video else None
        if video is None:
            shutil.copy(p, out / "audio_src" + p.suffix) if False else None
    json.dump(
        dossier["meta"], open(out / "meta.json", "w"), ensure_ascii=False, indent=1
    )
    # audio
    audio = out / "audio.wav"
    if not audio.exists():
        run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(video or src),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                str(audio),
            ]
        )
    dossier["audio"] = str(audio)
    kept = []
    if video:
        frames_dir = out / "frames"
        if not any(frames_dir.glob("f_*.jpg")):
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(video),
                    "-vf",
                    f"fps=1/{a.every},scale=1280:-1",
                    "-q:v",
                    "3",
                    str(frames_dir / "f_%05d.jpg"),
                ]
            )
        frames = sorted(frames_dir.glob("f_*.jpg"))
        dossier["n_frames"] = len(frames)
        last_hash = None
        n_with = 0
        for i, f in enumerate(frames):
            t = i * a.every
            im = Image.open(f)
            gray = np.asarray(im.convert("L"))
            ok, groups = has_sheet_music(gray)
            if not ok:
                continue
            n_with += 1
            top = max(0, groups[0][0] - 110)   # keep the chord-symbol row above the first staff
            bot = min(gray.shape[0], groups[-1][-1] + 90)   # and lyrics below the last staff
            crop = im.crop((0, top, im.width, bot))
            h = dhash(crop)
            if last_hash is not None and hamming(h, last_hash) < a.min_diff:
                continue
            last_hash = h
            cp = out / "crops" / f"c_{int(t):05d}s.jpg"
            crop.save(cp, quality=85)
            kept.append(
                {
                    "t": t,
                    "frame": f.name,
                    "crop": cp.name,
                    "band": [int(top), int(bot)],
                    "staves": len(groups),
                    "lines": int(sum(len(g) for g in groups)),
                }
            )
            if len(kept) >= a.max_keep:
                break
        dossier["frames_with_sheet_music"] = n_with
    dossier["kept"] = kept
    # contact sheets: 6 crops per page, full width
    sheets = []
    if kept:
        per = 6
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        except Exception:
            font = ImageFont.load_default()
        for s in range(0, len(kept), per):
            chunk = kept[s : s + per]
            crops = [Image.open(out / "crops" / k["crop"]) for k in chunk]
            W = 1280
            H = sum(int(c.height * W / c.width) + 34 for c in crops) + 10
            sheet = Image.new("RGB", (W, H), "white")
            d = ImageDraw.Draw(sheet)
            y = 5
            for k, c in zip(chunk, crops):
                d.text(
                    (8, y + 6),
                    f"t = {k['t']:.0f} s   ({k['frame']})",
                    fill=(170, 30, 30),
                    font=font,
                )
                y += 34
                c2 = c.resize((W, int(c.height * W / c.width)))
                sheet.paste(c2, (0, y))
                y += c2.height
            name = f"sheet_{s // per + 1:02d}.jpg"
            sheet.save(out / "sheets" / name, quality=82)
            sheets.append(
                {
                    "name": name,
                    "from_s": chunk[0]["t"],
                    "to_s": chunk[-1]["t"],
                    "n": len(chunk),
                }
            )
    dossier["sheets"] = sheets
    json.dump(dossier, open(out / "dossier.json", "w"), ensure_ascii=False, indent=1)
    print(
        json.dumps(
            {
                "title": dossier["meta"].get("title"),
                "duration": dossier["meta"].get("duration"),
                "frames": dossier.get("n_frames"),
                "with_sheet_music": dossier.get("frames_with_sheet_music"),
                "kept": len(kept),
                "sheets": len(sheets),
                "audio": str(audio),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
