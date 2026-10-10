#!/usr/bin/env python3
"""Hitung total baris kode & bahasa dari semua repo milik sendiri, lalu buat kartu SVG.

Env:
  GH_TOKEN       (wajib) Personal Access Token dengan scope `repo`
  GH_USER        username GitHub (default: NoName-LastMan)
  EXCLUDE_REPOS  daftar repo yang dilewati, pisahkan koma
  IGNORE_LANGS   bahasa non-kode yang diabaikan, pisahkan koma
"""
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "NoName-LastMan")
TOKEN = os.environ["GH_TOKEN"]
EXCLUDE = {r.strip() for r in os.environ.get("EXCLUDE_REPOS", USER).split(",") if r.strip()}
IGNORE = {
    l.strip()
    for l in os.environ.get(
        "IGNORE_LANGS", "JSON,Markdown,YAML,XML,SVG,CSV,Text,TOML"
    ).split(",")
    if l.strip()
}

COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "Java": "#b07219", "PHP": "#4F5D95", "Go": "#00ADD8", "C++": "#f34b7d",
    "C": "#aaaaaa", "HTML": "#e34c26", "CSS": "#663399", "SCSS": "#c6538c",
    "Sass": "#a53b70", "Vuejs Component": "#41b883", "Svelte": "#ff3e00",
    "Rust": "#dea584", "Dart": "#00B4AB", "Kotlin": "#A97BFF",
    "Bourne Shell": "#89e051", "Dockerfile": "#384d54", "Blade": "#f7523f",
    "SQL": "#e38c00", "Lua": "#000080", "Ruby": "#701516", "C#": "#178600",
    "Lainnya": "#6e7681",
}


def api(url):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "code-stats-script",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def list_repos():
    repos, page = [], 1
    while True:
        data = api(
            f"https://api.github.com/user/repos?affiliation=owner&per_page=100&page={page}"
        )
        if not data:
            break
        repos += data
        page += 1
    return [
        r for r in repos
        if not r["fork"]
        and r["owner"]["login"].lower() == USER.lower()
        and r["name"] not in EXCLUDE
        and r["full_name"] not in EXCLUDE
    ]


def count_repo(full_name, workdir):
    dest = os.path.join(workdir, full_name.replace("/", "__"))
    url = f"https://x-access-token:{TOKEN}@github.com/{full_name}.git"
    clone = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", url, dest],
        capture_output=True, text=True,
    )
    if clone.returncode != 0:
        print(f"  ! gagal clone {full_name} (mungkin kosong)", file=sys.stderr)
        return {}
    out = subprocess.run(
        ["cloc", "--vcs=git", "--json", "--quiet",
         r"--not-match-f=\.min\.(js|css)$", "."],
        cwd=dest, capture_output=True, text=True,
    )
    shutil.rmtree(dest, ignore_errors=True)
    if not out.stdout.strip():
        return {}
    data = json.loads(out.stdout)
    return {
        k: v for k, v in data.items()
        if k not in ("header", "SUM") and k not in IGNORE
    }


def fmt(n):
    return f"{n:,}".replace(",", ".")


def esc(s):
    return html.escape(str(s))


def build_svg(total, files, n_repos, langs):
    top = langs[:10]
    rest = sum(c for _, c, _ in langs[10:])
    segments = list(top)
    if rest:
        segments.append(("Lainnya", rest, 0))

    W, PAD, BAR_W = 800, 40, 720
    rows = (len(top) + 1) // 2
    H = 200 + rows * 30 + 30

    # stacked bar
    bar, x = [], PAD
    for name, code, _ in segments:
        w = BAR_W * code / total if total else 0
        bar.append(
            f'<rect x="{x:.2f}" y="132" width="{w:.2f}" height="12" '
            f'fill="{COLORS.get(name, "#8b949e")}"/>'
        )
        x += w

    # legenda
    legend = []
    for i, (name, code, nfiles) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = PAD + col * 370, 185 + row * 30
        pct = 100 * code / total if total else 0
        legend.append(
            f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="{COLORS.get(name, "#8b949e")}"/>'
            f'<text x="{lx + 20}" y="{ly}" class="lang">{esc(name)}</text>'
            f'<text x="{lx + 340}" y="{ly}" class="val" text-anchor="end">'
            f'{fmt(code)} baris · {pct:.1f}%</text>'
        )

    updated = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Total {fmt(total)} baris kode">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0f0c29"/><stop offset="0.5" stop-color="#302b63"/><stop offset="1" stop-color="#24243e"/>
    </linearGradient>
    <clipPath id="round"><rect x="{PAD}" y="132" width="{BAR_W}" height="12" rx="6"/></clipPath>
  </defs>
  <style>
    text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif; }}
    .title {{ fill: #00f7ff; font-size: 14px; font-weight: 600; letter-spacing: 1px; }}
    .big {{ fill: #ffffff; font-size: 44px; font-weight: 700; }}
    .sub {{ fill: #b8b5d6; font-size: 14px; }}
    .lang {{ fill: #ffffff; font-size: 14px; font-weight: 600; }}
    .val {{ fill: #b8b5d6; font-size: 13px; }}
    .foot {{ fill: #8581b0; font-size: 11px; }}
  </style>
  <rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="#7b2ff7" stroke-opacity="0.5"/>
  <text x="{PAD}" y="42" class="title">TOTAL KODE YANG SUDAH DITULIS</text>
  <text x="{PAD}" y="92" class="big">{fmt(total)} <tspan class="sub" font-size="18">baris kode</tspan></text>
  <text x="{PAD}" y="115" class="sub">{fmt(files)} file · {n_repos} repo · {len(langs)} bahasa</text>
  <g clip-path="url(#round)"><rect x="{PAD}" y="132" width="{BAR_W}" height="12" fill="#1c1a3a"/>{''.join(bar)}</g>
  {''.join(legend)}
  <text x="{W - PAD}" y="{H - 14}" class="foot" text-anchor="end">Diperbarui {updated}</text>
</svg>
"""


def main():
    repos = list_repos()
    print(f"Menghitung {len(repos)} repo...")
    totals = {}  # bahasa -> [code, files]
    workdir = tempfile.mkdtemp()
    counted = 0
    try:
        for r in repos:
            print(f"- {r['full_name']}")
            res = count_repo(r["full_name"], workdir)
            if res:
                counted += 1
            for lang, v in res.items():
                t = totals.setdefault(lang, [0, 0])
                t[0] += v["code"]
                t[1] += v["nFiles"]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    langs = sorted(((l, c, f) for l, (c, f) in totals.items()), key=lambda x: -x[1])
    total = sum(c for _, c, _ in langs)
    files = sum(f for _, _, f in langs)

    os.makedirs("assets", exist_ok=True)
    with open("assets/code-stats.svg", "w", encoding="utf-8") as fh:
        fh.write(build_svg(total, files, counted, langs))
    with open("assets/code-stats.json", "w", encoding="utf-8") as fh:
        json.dump(
            {"total_lines": total, "files": files, "repos": counted,
             "languages": [{"name": l, "lines": c, "files": f} for l, c, f in langs]},
            fh, indent=2, ensure_ascii=False,
        )
    print(f"Selesai: {fmt(total)} baris, {len(langs)} bahasa.")


if __name__ == "__main__":
    main()
