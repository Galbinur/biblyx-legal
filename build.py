#!/usr/bin/env python3
"""Builds the guide pages of biblyx.com and the sitemap. Standard library only.

Content lives in guides/<slug>/<lang>.md: a front-matter block between two
`---` lines, then a small Markdown subset (## and ### headings, paragraphs,
- and 1. lists, > quotes, | tables |, **bold**, *italic*, `code`, [text](url)).
The FAQ is the section whose ## heading equals the front matter's `faq`
value; each ### inside it is a question and the paragraphs under it the
answer (they become FAQPage JSON-LD too).

Front matter keys: title (the <title> and og:title), h1 (default: title),
description (meta description), path (URL slug for this language; default:
the folder name), date (first published, YYYY-MM-DD), author, image
(default /og-image-<lang>.png), cta (Play button line; default per language),
faq (the FAQ heading), slogan (the slogan line in this language, checked once).

Output: /<path>/index.html for en, /<lang>/<path>/index.html for the others,
with hreflang across the languages that exist for the slug (x-default = en),
Article + FAQPage + BreadcrumbList JSON-LD, the locale home page's footer and
UTM-forwarding script copied in, and sitemap.xml rebuilt with lastmod from git.

  python3 build.py                 build everything into the repo
  python3 build.py --check         build and run the checks only (no writes)
  python3 build.py --out DIR       build into another directory (dry run)
  python3 build.py --drafts        include guides/_*/ folders too

Folders starting with "_" are drafts and are skipped unless --drafts is given.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = "https://biblyx.com"
LANGS = ["en", "tr", "az", "de", "es", "fr", "it", "ru", "pl", "pt"]
LANG_NAMES = {"en": "English", "tr": "Türkçe", "az": "Azərbaycan", "de": "Deutsch", "es": "Español",
              "fr": "Français", "it": "Italiano", "ru": "Русский", "pl": "Polski", "pt": "Português"}
OG_LOCALE = {"en": "en_US", "tr": "tr_TR", "az": "az_AZ", "de": "de_DE", "es": "es_ES", "fr": "fr_FR",
             "it": "it_IT", "ru": "ru_RU", "pl": "pl_PL", "pt": "pt_BR"}
PLAY = "https://play.google.com/store/apps/details?id=com.biblyx.app"

# Short interface strings of the guide pages. Draft translations; a native
# reader checks them with the first guide of each language.
UI = {
    "en": dict(home="Home", guides="Guides", updated="Updated", by="By", also="Read next",
               cta="Try it with your own book", button="Get Biblyx on Google Play", faq="Frequently asked questions"),
    "az": dict(home="Ana səhifə", guides="Bələdçilər", updated="Yenilənib", by="Müəllif", also="Bunları da oxu",
               cta="Öz kitabınla sına", button="Biblyx-i Google Play-dən yüklə", faq="Tez-tez verilən suallar"),
    "tr": dict(home="Ana sayfa", guides="Rehberler", updated="Güncellendi", by="Yazar", also="Bunları da oku",
               cta="Kendi kitabınla dene", button="Biblyx'i Google Play'den indir", faq="Sık sorulan sorular"),
    "ru": dict(home="Главная", guides="Руководства", updated="Обновлено", by="Автор", also="Читайте также",
               cta="Попробуйте со своей книгой", button="Скачать Biblyx в Google Play", faq="Частые вопросы"),
    "de": dict(home="Startseite", guides="Ratgeber", updated="Aktualisiert", by="Von", also="Weiterlesen",
               cta="Mit dem eigenen Buch ausprobieren", button="Biblyx bei Google Play laden", faq="Häufige Fragen"),
    "es": dict(home="Inicio", guides="Guías", updated="Actualizado", by="Por", also="Sigue leyendo",
               cta="Pruébalo con tu propio libro", button="Descargar Biblyx en Google Play", faq="Preguntas frecuentes"),
    "fr": dict(home="Accueil", guides="Guides", updated="Mis à jour", by="Par", also="À lire aussi",
               cta="Essayez avec votre propre livre", button="Télécharger Biblyx sur Google Play", faq="Questions fréquentes"),
    "it": dict(home="Home", guides="Guide", updated="Aggiornato", by="Di", also="Leggi anche",
               cta="Provalo con un tuo libro", button="Scarica Biblyx su Google Play", faq="Domande frequenti"),
    "pl": dict(home="Strona główna", guides="Poradniki", updated="Zaktualizowano", by="Autor", also="Czytaj dalej",
               cta="Wypróbuj z własną książką", button="Pobierz Biblyx z Google Play", faq="Częste pytania"),
    "pt": dict(home="Início", guides="Guias", updated="Atualizado", by="Por", also="Leia também",
               cta="Experimente com o seu próprio livro", button="Baixar o Biblyx no Google Play", faq="Perguntas frequentes"),
}

BRAND_SVG = """<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs><mask id="lens" maskUnits="userSpaceOnUse" x="0" y="0" width="400" height="400">
        <rect x="0" y="0" width="400" height="400" fill="#fff"></rect>
        <path d="M200 88 A115 115 0 0 1 200 312 A115 115 0 0 1 200 88 Z" fill="#000"></path></mask></defs>
      <g mask="url(#lens)" fill="var(--ink)"><circle cx="155" cy="200" r="115"></circle><circle cx="245" cy="200" r="115"></circle></g>
      <circle cx="200" cy="200" r="21" fill="var(--gold)"></circle>
    </svg>"""


# ----------------------------------------------------------------------------- content

def parse_front_matter(text: str):
    if not text.startswith("---"):
        raise ValueError("missing front matter")
    _, fm, body = text.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body.strip("\n")


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    # The URL was escaped with the rest of the line above; unescape before quoting it for the attribute.
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(html.unescape(m.group(2)), quote=True)}">{m.group(1)}</a>', s)
    return s


def render_markdown(body: str, faq_heading: str):
    """Returns (html, faq) where faq is a list of (question, answer_text)."""
    out, faq = [], []
    lines = body.splitlines()
    i, in_faq, q, q_paras = 0, False, None, []

    def flush_q():
        nonlocal q, q_paras
        if q is not None:
            faq.append((q, " ".join(q_paras)))
        q, q_paras = None, []

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("## "):
            flush_q()
            text = line[3:].strip()
            in_faq = text == faq_heading
            out.append(f'<h2 id="{slugify(text)}">{inline(text)}</h2>')
        elif line.startswith("### "):
            flush_q()
            text = line[4:].strip()
            if in_faq:
                q = text
            out.append(f'<h3 id="{slugify(text)}">{inline(text)}</h3>')
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:].strip())}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(f"<li>{inline(re.sub(r'^\d+\. ', '', lines[i]).strip())}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif line.startswith("> "):
            quote = []
            while i < len(lines) and lines[i].startswith("> "):
                quote.append(inline(lines[i][2:].strip()))
                i += 1
            out.append("<blockquote><p>" + " ".join(quote) + "</p></blockquote>")
            continue
        elif re.match(r"^!\[[^\]]*\]\([^)\s]+\)\s*$", line):
            # A line with only an image: ![alt](src), shown as a figure (app screenshots, 720x1280).
            m = re.match(r"^!\[([^\]]*)\]\(([^)\s]+)\)", line)
            out.append(f'<figure class="shot"><img src="{html.escape(m.group(2), quote=True)}" '
                       f'alt="{html.escape(m.group(1), quote=True)}" loading="lazy" width="720" height="1280"></figure>')
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            head, *rest = rows
            thead = "".join(f"<th>{inline(c)}</th>" for c in head)
            tbody = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rest)
            out.append(f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
            continue
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,3} |- |\d+\. |> |\||!\[)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            text = " ".join(para)
            out.append(f"<p>{inline(text)}</p>")
            if q is not None:
                q_paras.append(text)
            continue
        i += 1
    flush_q()
    return "\n".join(out), faq


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower(), flags=re.U)
    return re.sub(r"[\s_]+", "-", s).strip("-")[:60] or "s"


def visible_words(fragment: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", fragment).split())


# ----------------------------------------------------------------------------- repo pieces

def home_page(lang: str) -> str:
    p = ROOT / ("index.html" if lang == "en" else f"{lang}/index.html")
    return p.read_text(encoding="utf-8")


def footer_of(lang: str) -> str:
    m = re.search(r"<footer class=\"wrap\">.*?</footer>", home_page(lang), re.S)
    if not m:
        raise RuntimeError(f"no footer in the {lang} home page")
    # The language row marks the home page as current; on a guide nothing is.
    return m.group(0).replace(' aria-current="page"', "")


def utm_script() -> str:
    m = re.search(r"<script>\s*// Forward this page's utm_\*.*?</script>", home_page("en"), re.S)
    return m.group(0) if m else ""


def git_date(path: Path) -> str:
    rel = str(path.relative_to(ROOT))
    status = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout
    if status.strip():
        return dt.date.today().isoformat()
    out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return out or dt.date.today().isoformat()


# ----------------------------------------------------------------------------- guides

def url_for(lang: str, path: str) -> str:
    return f"{SITE}/{path}/" if lang == "en" else f"{SITE}/{lang}/{path}/"


def home_url(lang: str) -> str:
    return f"{SITE}/" if lang == "en" else f"{SITE}/{lang}/"


def load_guides(include_drafts: bool):
    guides = {}
    gdir = ROOT / "guides"
    if not gdir.exists():
        return guides
    for folder in sorted(p for p in gdir.iterdir() if p.is_dir()):
        if folder.name.startswith("_") and not include_drafts:
            continue
        pages = {}
        for md in sorted(folder.glob("*.md")):
            lang = md.stem
            if lang not in LANGS:
                continue
            meta, body = parse_front_matter(md.read_text(encoding="utf-8"))
            meta.setdefault("path", folder.name)
            meta.setdefault("h1", meta["title"])
            meta.setdefault("author", "Galbinur Guliyev")
            meta.setdefault("faq", UI[lang]["faq"])
            meta.setdefault("image", f"/og-image-{lang}.png" if lang != "en" else "/og-image.png")
            meta["lang"], meta["source"] = lang, md
            meta["updated"] = git_date(md)
            meta.setdefault("date", meta["updated"])
            pages[lang] = (meta, body)
        if pages:
            guides[folder.name] = pages
    return guides


def render_guide(slug: str, lang: str, meta: dict, body: str, siblings: dict, all_guides: dict) -> str:
    ui = UI[lang]
    content, faq = render_markdown(body, meta["faq"])
    url = url_for(lang, meta["path"])
    alternates = {l: url_for(l, m["path"]) for l, (m, _) in siblings.items()}
    x_default = alternates.get("en", alternates[sorted(alternates)[0]])
    campaign = f"guide_{slug}_{lang}".replace("-", "_")
    referrer = f"utm_source%3Dbiblyx.com%26utm_medium%3Dwebsite%26utm_campaign%3D{campaign}"
    play = f"{PLAY}&referrer={referrer}"

    ld = [{
        "@type": "Article",
        "@id": url + "#article",
        "headline": meta["h1"],
        "description": meta["description"],
        "inLanguage": lang,
        "datePublished": meta["date"],
        "dateModified": meta["updated"],
        "author": {"@type": "Person", "name": meta["author"]},
        "publisher": {"@type": "Organization", "name": "Biblyx", "url": SITE + "/",
                      "logo": {"@type": "ImageObject", "url": SITE + "/apple-touch-icon.png"}},
        "mainEntityOfPage": url,
        "image": SITE + meta["image"],
    }, {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Biblyx", "item": home_url(lang)},
            {"@type": "ListItem", "position": 2, "name": ui["guides"], "item": home_url(lang) + "#guides"},
            {"@type": "ListItem", "position": 3, "name": meta["h1"], "item": url},
        ],
    }]
    if faq:
        ld.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    ld_json = json.dumps({"@context": "https://schema.org", "@graph": ld}, ensure_ascii=False, indent=1)

    hreflangs = "\n".join(f'<link rel="alternate" hreflang="{l}" href="{u}">' for l, u in sorted(alternates.items()))
    hreflangs += f'\n<link rel="alternate" hreflang="x-default" href="{x_default}">'
    options = "\n".join(f'      <option value="{u.replace(SITE, "")}"{" selected" if l == lang else ""}>{LANG_NAMES[l]}</option>'
                        for l, u in sorted(alternates.items(), key=lambda kv: LANGS.index(kv[0])))
    others = [(s, p[lang][0]) for s, p in all_guides.items() if s != slug and lang in p]
    also = ""
    if others:
        items = "".join(f'<li><a href="{url_for(lang, m["path"]).replace(SITE, "")}">{html.escape(m["h1"])}</a></li>' for _, m in others)
        also = f'<aside class="also"><h2>{ui["also"]}</h2><ul>{items}</ul></aside>'
    esc = lambda s: html.escape(s, quote=True)
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-YLNHMNQKMY"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-YLNHMNQKMY');
</script>
<title>{esc(meta["title"])}</title>
<meta name="description" content="{esc(meta["description"])}">
<link rel="canonical" href="{url}">
{hreflangs}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
<meta name="theme-color" content="#14383B">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Biblyx">
<meta property="og:locale" content="{OG_LOCALE[lang]}">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(meta["title"])}">
<meta property="og:description" content="{esc(meta["description"])}">
<meta property="og:image" content="{SITE}{meta["image"]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(meta["title"])}">
<meta name="twitter:description" content="{esc(meta["description"])}">
<meta name="twitter:image" content="{SITE}{meta["image"]}">
<link rel="stylesheet" href="/assets/guide.css">
<script type="application/ld+json">
{ld_json}
</script>
</head>
<body>

<nav class="wrap">
  <a class="brand" href="{home_url(lang).replace(SITE, "") or "/"}">
    {BRAND_SVG}
    <span class="wordmark">Biblyx</span>
  </a>
  <div class="links">
    <a href="{home_url(lang).replace(SITE, "") or "/"}">{ui["home"]}</a>
    <a href="{home_url(lang).replace(SITE, "") or "/"}#guides">{ui["guides"]}</a>
  </div>
  <select class="lang-switch" aria-label="Language" onchange="location.href=this.value">
{options}
  </select>
</nav>

<main class="wrap article">
  <article>
    <header>
      <h1>{inline(meta["h1"])}</h1>
      <p class="meta">{ui["by"]} {esc(meta["author"])} · {ui["updated"]}: <time datetime="{meta["updated"]}">{meta["updated"]}</time></p>
    </header>
{content}
  </article>
  <aside class="cta">
    <h2>{ui["cta"]}</h2>
    <p>{esc(meta.get("cta", ""))}</p>
    <a class="btn btn-primary" href="{play}" target="_blank" rel="noopener">{ui["button"]}</a>
  </aside>
  {also}
</main>

{footer_of(lang)}

{utm_script()}

</body>
</html>
"""


# ----------------------------------------------------------------------------- sitemap

def build_sitemap(guides: dict) -> str:
    def url_block(loc: str, lastmod: str, alts: dict, x_default: str) -> str:
        links = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{u}"/>' for l, u in sorted(alts.items()))
        links += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{x_default}"/>'
        return f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>{links}\n  </url>"

    blocks = []
    homes = {l: home_url(l) for l in LANGS}
    for l in LANGS:
        src = ROOT / ("index.html" if l == "en" else f"{l}/index.html")
        blocks.append(url_block(homes[l], git_date(src), homes, homes["en"]))
    for slug, pages in guides.items():
        alts = {l: url_for(l, m["path"]) for l, (m, _) in pages.items()}
        x_default = alts.get("en", alts[sorted(alts)[0]])
        for l, (m, _) in pages.items():
            blocks.append(url_block(alts[l], m["updated"], alts, x_default))
    for page in ("privacy-policy", "terms", "account-deletion"):
        blocks.append(f"  <url>\n    <loc>{SITE}/{page}</loc>\n    <lastmod>{git_date(ROOT / (page + '.html'))}</lastmod>\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(blocks) + "\n</urlset>\n")


# ----------------------------------------------------------------------------- checks

def check_page(lang: str, meta: dict, page: str, warnings: list):
    where = f"{meta['source'].relative_to(ROOT)}"
    from html.parser import HTMLParser

    class P(HTMLParser):
        depth = 0
        bad = []
        void = {"meta", "link", "br", "img", "input", "hr", "source"}

        def handle_starttag(self, tag, attrs):
            if tag not in self.void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in self.void:
                return
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            else:
                self.bad.append(tag)

    p = P()
    p.stack = []
    p.feed(page)
    if p.bad or p.stack:
        warnings.append(f"{where}: HTML tags don't balance: {p.bad[:3]} {p.stack[:3]}")
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        json.loads(m.group(1))
    if len(meta["title"]) > 60:
        warnings.append(f"{where}: title is {len(meta['title'])} characters (keep ≤ 60)")
    if not 110 <= len(meta["description"]) <= 165:
        warnings.append(f"{where}: description is {len(meta['description'])} characters (aim 120–160)")
    words = visible_words(re.search(r"<article>.*?</article>", page, re.S).group(0))
    if words < 600 and meta.get("short") != "yes":
        warnings.append(f"{where}: only {words} words in the article (aim 700+)")
    slogan = meta.get("slogan")
    if slogan:
        n = page.count(slogan)
        if n != 1:
            warnings.append(f"{where}: the slogan appears {n} times (expected once)")
    else:
        warnings.append(f"{where}: no `slogan:` line in the front matter, so the slogan check is skipped")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write into this directory instead of the repo")
    ap.add_argument("--check", action="store_true", help="build in memory and report checks only")
    ap.add_argument("--drafts", action="store_true", help="include guides/_*/ folders")
    args = ap.parse_args()
    out_root = Path(args.out).resolve() if args.out else ROOT
    guides = load_guides(args.drafts)
    warnings, written = [], []
    for slug, pages in guides.items():
        for lang, (meta, body) in pages.items():
            page = render_guide(slug, lang, meta, body, pages, guides)
            check_page(lang, meta, page, warnings)
            rel = Path(meta["path"]) / "index.html" if lang == "en" else Path(lang) / meta["path"] / "index.html"
            if not args.check:
                target = out_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(page, encoding="utf-8")
                written.append(str(rel))
    sitemap = build_sitemap(guides)
    if not args.check:
        (out_root / "sitemap.xml").write_text(sitemap, encoding="utf-8")
        written.append("sitemap.xml")
    print(f"guides: {sum(len(p) for p in guides.values())} pages in {len(guides)} folders; sitemap URLs: {sitemap.count('<loc>')}")
    for w in written:
        print("  wrote", w)
    for w in warnings:
        print("  warn:", w)
    return 1 if any("don't balance" in w for w in warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
