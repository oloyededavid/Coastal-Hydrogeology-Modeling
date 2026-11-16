"""Stage 7: build docs/index.html from paper/paper.md, so the page and the paper cannot disagree (the same pattern
as the other study sites). The paper points to figures/audit-2026-11/*.png; the page shows the WebP copies that
p04_figures.py writes to docs/assets/figures/, with a narrower *_phone.webp for small screens.

    python3 code/pipeline/p06_build_paper.py && python3 code/pipeline/p07_build_page.py
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIG = re.compile(r"!\[(\*\*Figure (\d+)\.\*\* )?(.*?)\]\(figures/audit-2026-11/([^)]+)\.png\)")
DESCRIPTION = ("Urban sealing on the Lekki-Epe barrier, Lagos, 1986-2024, from open satellite data, and an uncalibrated "
               "MODFLOW 6 scenario model of what it could do to the shallow water table.")


def image_size(rel):
    from PIL import Image
    with Image.open(ROOT / "docs" / rel) as im:
        return im.size


def figure_html(m):
    num, desc, stem = m.group(2), m.group(3), m.group(4)
    alt = re.sub(r"\*\*", "", desc).replace('"', "&quot;")
    src, phone = f"assets/figures/{stem}.webp", f"assets/figures/{stem}_phone.webp"
    w, h = image_size(src)
    pic = (f'<picture><source media="(max-width: 760px)" srcset="{phone}">'
           f'<img src="{src}" width="{w}" height="{h}" loading="lazy" alt="{alt}"></picture>')
    return f'<figure class="wide" id="fig-{num}">{pic}<figcaption><b>Figure {num}.</b> {desc}</figcaption></figure>'


def tidy(html):
    parts = re.split(r"(<[^>]+>)", html)
    unit = re.compile(r"(\d) (mm|km|km²|m|cm|%)\b")
    return "".join(p if p.startswith("<") else unit.sub("\\1\u00a0\\2", p) for p in parts)


def study_links(html, docs):
    """Insert the study bar and next-study card kept in docs/assets/study-*.html (written by the portfolio's
    tools/sync_nav.py once this study is on the portfolio; drafts until then)."""
    for key, where in (("study-bar", "top"), ("study-nav", "end")):
        f = docs / "assets" / f"{key}.html"
        if not f.exists():
            continue
        block = f.read_text(encoding="utf-8").strip()
        html = re.sub(rf"<!-- {key}:start -->.*?<!-- {key}:end -->\n?", "", html, flags=re.S)
        html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + block, html, count=1) if where == "top" else html.replace("</body>", block + "\n</body>", 1)
    return html


def main():
    md = (ROOT / "paper" / "paper.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", md, flags=re.S)
    meta = dict(re.findall(r'^(\w+): "?([^"\n]*)"?$', m.group(1), flags=re.M)) if m else {}
    body = FIG.sub(figure_html, md[m.end():] if m else md)
    tmp = ROOT / "paper" / "_page_body.md"
    tmp.write_text(body, encoding="utf-8")
    out = ROOT / "docs" / "index.html"
    try:
        subprocess.run(["pandoc", str(tmp), "-f", "markdown-raw_html+raw_html", "-t", "html5", "--shift-heading-level-by=1",
                        "--template", str(Path(__file__).with_name("page_template.html")), "-o", str(out),
                        "--metadata", f"pagetitle={meta.get('title', '')}", "--metadata", f"title={meta.get('title', '')}",
                        "--metadata", f"author={meta.get('author', '')}", "--metadata", f"date={meta.get('date', '')}",
                        "--metadata", f"description={DESCRIPTION}"], check=True)
    finally:
        tmp.unlink(missing_ok=True)
    out.write_text(study_links(tidy(out.read_text(encoding="utf-8")), out.parent), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
