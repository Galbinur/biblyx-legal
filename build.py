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
import zipfile
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

ALL_GUIDES = {"en": "All guides", "tr": "Tüm rehberler", "az": "Bütün bələdçilər", "de": "Alle Ratgeber",
              "es": "Todas las guías", "fr": "Tous les guides", "it": "Tutte le guide", "ru": "Все руководства",
              "pl": "Wszystkie poradniki", "pt": "Todos os guias"}

# The guides index ("hub") of each language: /<path>/ for en, /<lang>/<path>/ for the others.
HUB = {
    "en": dict(path="reading-guides", title="Guides for learning a language by reading", h1="Guides",
               description="Guides on learning a language by reading: books for beginners by level, reading with translation, app comparisons and Biblyx release notes.",
               intro="Practical pages on learning a language by reading: which books to start with at your level, how a reader with translation works, how Biblyx compares with other apps, and what changed in each update."),
    "tr": dict(path="rehberler", title="Kitap okuyarak dil öğrenme rehberleri", h1="Rehberler",
               description="Kitap okuyarak dil öğrenme rehberleri: seviyeye göre başlangıç kitapları, çevirili okuma, uygulama karşılaştırmaları ve Biblyx sürüm notları.",
               intro="Kitap okuyarak dil öğrenmek üzerine pratik sayfalar: seviyene göre hangi kitaplarla başlamalı, çevirili okuyucu nasıl çalışır, Biblyx diğer uygulamalarla nasıl karşılaştırılır ve her güncelleme neyi değiştirdi."),
    "az": dict(path="beledciler", title="Kitab oxuyaraq dil öyrənmək üçün bələdçilər", h1="Bələdçilər",
               description="Kitab oxuyaraq dil öyrənmək üçün bələdçilər: səviyyəyə görə başlanğıc kitabları, tərcüməli oxu, tətbiqlərin müqayisəsi və Biblyx-in yenilikləri.",
               intro="Kitab oxuyaraq dil öyrənmək haqqında praktik səhifələr: səviyyənə görə hansı kitablarla başlamaq, tərcüməli oxuyucu necə işləyir, Biblyx digər tətbiqlərlə necə müqayisə olunur və hər yeniləmədə nə dəyişib."),
    "de": dict(path="ratgeber", title="Ratgeber: Sprachen lernen durch Lesen", h1="Ratgeber",
               description="Ratgeber zum Sprachenlernen durch Lesen: Bücher für Anfänger nach Niveau, Lesen mit Übersetzung, App-Vergleiche und die Neuerungen in Biblyx.",
               intro="Praktische Seiten zum Sprachenlernen mit Büchern: mit welchen Büchern du auf deinem Niveau anfängst, wie ein Reader mit Übersetzung funktioniert, wie Biblyx im Vergleich zu anderen Apps abschneidet und was sich mit jedem Update geändert hat."),
    "es": dict(path="guias", title="Guías para aprender idiomas leyendo", h1="Guías",
               description="Guías para aprender idiomas leyendo: libros para principiantes por nivel, lectura con traducción, comparativas de apps y novedades de Biblyx.",
               intro="Páginas prácticas sobre aprender idiomas leyendo: con qué libros empezar según tu nivel, cómo funciona un lector con traducción, cómo se compara Biblyx con otras apps y qué cambió en cada actualización."),
    "fr": dict(path="guides", title="Guides pour apprendre une langue en lisant", h1="Guides",
               description="Guides pour apprendre une langue en lisant : livres pour débutants par niveau, lecture avec traduction, comparatifs d'applis et nouveautés de Biblyx.",
               intro="Des pages pratiques pour apprendre une langue en lisant : par quels livres commencer selon votre niveau, comment fonctionne une liseuse avec traduction, comment Biblyx se compare aux autres applis et ce qui a changé à chaque mise à jour."),
    "it": dict(path="guide", title="Guide per imparare le lingue leggendo", h1="Guide",
               description="Guide per imparare le lingue leggendo: libri per principianti per livello, lettura con traduzione, confronti tra app e novità di Biblyx.",
               intro="Pagine pratiche per imparare le lingue leggendo: con quali libri iniziare in base al tuo livello, come funziona un lettore con traduzione, come si confronta Biblyx con le altre app e cosa è cambiato a ogni aggiornamento."),
    "ru": dict(path="rukovodstva", title="Руководства: как учить язык, читая книги", h1="Руководства",
               description="Руководства по изучению языков через чтение: книги для начинающих по уровням, чтение с переводом, сравнение приложений и новости Biblyx.",
               intro="Практические страницы о том, как учить язык через чтение: с каких книг начать на вашем уровне, как работает читалка с переводом, чем Biblyx отличается от других приложений и что изменилось в каждом обновлении."),
    "pl": dict(path="poradniki", title="Poradniki: nauka języków przez czytanie", h1="Poradniki",
               description="Poradniki o nauce języków przez czytanie: książki dla początkujących według poziomu, czytanie z tłumaczeniem, porównania aplikacji i nowości Biblyx.",
               intro="Praktyczne strony o nauce języków przez czytanie: od jakich książek zacząć na twoim poziomie, jak działa czytnik z tłumaczeniem, jak Biblyx wypada na tle innych aplikacji i co zmieniło się w każdej aktualizacji."),
    "pt": dict(path="guias", title="Guias para aprender idiomas lendo", h1="Guias",
               description="Guias para aprender idiomas lendo: livros para iniciantes por nível, leitura com tradução, comparação de apps e novidades do Biblyx.",
               intro="Páginas práticas sobre aprender idiomas lendo: com quais livros começar no seu nível, como funciona um leitor com tradução, como o Biblyx se compara a outros apps e o que mudou em cada atualização."),
}

# The slogan, word for word (dil-okuma-app docs/decisions.md).
SLOGAN = {"en": "Learn languages by reading your own books", "az": "Öz kitablarını oxuyaraq dil öyrən",
          "tr": "Kendi kitaplarını okuyarak dil öğren", "ru": "Учите языки, читая свои книги",
          "de": "Sprachen lernen beim Lesen deiner eigenen Bücher", "es": "Aprende idiomas leyendo tus propios libros",
          "fr": "Apprenez les langues en lisant vos propres livres", "it": "Impara le lingue leggendo i tuoi libri",
          "pl": "Ucz się języków, czytając własne książki", "pt": "Aprenda idiomas lendo seus próprios livros"}

# Filled in by main(): the story library texts per language (stories/library.json) and the guides.
CTX = {"library": {}, "stories": {}, "guides": {}}

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
    m = re.search(r"<footer class=\"wrap\">.*?</footer>", home_with_rows(lang), re.S)
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
            {"@type": "ListItem", "position": 2, "name": ui["guides"], "item": hub_url(lang)},
            {"@type": "ListItem", "position": 3, "name": meta["h1"], "item": url},
        ],
    }]
    if faq:
        ld.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    others = [(s, p[lang][0]) for s, p in all_guides.items() if s != slug and lang in p and p[lang][0].get("listed") != "no"]
    also = ""
    if others:
        items = "".join(f'<li><a href="{url_for(lang, m["path"]).replace(SITE, "")}">{html.escape(m["h1"])}</a></li>' for _, m in others)
        also = f'<aside class="also"><h2>{ui["also"]}</h2><ul>{items}</ul></aside>'
    main = f"""<main class="wrap article">
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
</main>"""
    return page_shell(lang, title=meta["title"], description=meta["description"], url=url, alternates=alternates,
                      og_type="article", image=meta["image"], ld=ld, main=main)


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def rel(url: str) -> str:
    return url.replace(SITE, "") or "/"


def hub_url(lang: str) -> str:
    return url_for(lang, HUB[lang]["path"])


def nav_html(lang: str, alternates: dict) -> str:
    options = "\n".join(f'      <option value="{rel(u)}"{" selected" if l == lang else ""}>{LANG_NAMES[l]}</option>'
                        for l, u in sorted(alternates.items(), key=lambda kv: LANGS.index(kv[0])))
    links = [f'<a href="{rel(home_url(lang))}">{UI[lang]["home"]}</a>', f'<a href="{rel(hub_url(lang))}">{UI[lang]["guides"]}</a>']
    lib = CTX["library"].get(lang)
    if lib:
        links.append(f'<a href="{rel(url_for(lang, lib["path"]))}">{esc(lib["crumb"])}</a>')
    return f"""<nav class="wrap">
  <a class="brand" href="{rel(home_url(lang))}">
    {BRAND_SVG}
    <span class="wordmark">Biblyx</span>
  </a>
  <div class="links">
    {"\n    ".join(links)}
  </div>
  <select class="lang-switch" aria-label="Language" onchange="location.href=this.value">
{options}
  </select>
</nav>"""


def page_shell(lang: str, *, title: str, description: str, url: str, alternates: dict, og_type: str,
               image: str, ld: list, main: str, scripts: str = "") -> str:
    x_default = alternates.get("en", alternates[sorted(alternates)[0]])
    hreflangs = "\n".join(f'<link rel="alternate" hreflang="{l}" href="{u}">' for l, u in sorted(alternates.items()))
    hreflangs += f'\n<link rel="alternate" hreflang="x-default" href="{x_default}">'
    ld_json = json.dumps({"@context": "https://schema.org", "@graph": ld}, ensure_ascii=False, indent=1).replace("</", "<\\/")
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
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
{hreflangs}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
<meta name="theme-color" content="#14383B">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Biblyx">
<meta property="og:locale" content="{OG_LOCALE[lang]}">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{SITE}{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{SITE}{image}">
<link rel="stylesheet" href="/assets/guide.css">
<script type="application/ld+json">
{ld_json}
</script>
</head>
<body>

{nav_html(lang, alternates)}

{main}

{footer_of(lang)}

{utm_script()}
{scripts}
</body>
</html>
"""


# ----------------------------------------------------------------------------- home pages: generated rows

FOOT_MARK = ("<!-- build:foot-hub -->", "<!-- /build:foot-hub -->")
GUIDES_MARK = ("<!-- build:guides-all -->", "<!-- /build:guides-all -->")
_home_cache = {}


def _put_block(page: str, marks: tuple, block: str, before: str) -> str:
    """Puts `block` between the two marker comments; adds the markers before `before` the first time."""
    start, end = marks
    wrapped = f"{start}\n{block}\n  {end}"
    if start in page:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: wrapped, page, count=1, flags=re.S)
    i = page.find(before)
    if i < 0:
        raise RuntimeError(f"can't place {start}: {before!r} not found")
    line_start = page.rfind("\n", 0, i) + 1
    return page[:line_start] + "  " + wrapped + "\n" + page[line_start:]


def home_with_rows(lang: str) -> str:
    """The home page with the generated "all guides" line and the footer row (guides index, story library)."""
    if lang in _home_cache:
        return _home_cache[lang]
    page = home_page(lang)
    lib = CTX["library"].get(lang)
    foot = [f'<a href="{rel(hub_url(lang))}">{UI[lang]["guides"]}</a>']
    more = [f'<a class="btn btn-secondary" href="{rel(hub_url(lang))}">{ALL_GUIDES[lang]} →</a>']
    if lib:
        foot.append(f'<a href="{rel(url_for(lang, lib["path"]))}">{esc(lib["crumb"])}</a>')
        more.append(f'<a class="btn btn-primary" href="{rel(url_for(lang, lib["path"]))}">{esc(lib["h1"])} →</a>')
    for src, (libs, _) in CTX["colls"].items():
        if src != "en" and lang in libs:
            foot.append(f'<a href="{rel(url_for(lang, libs[lang]["path"]))}">{esc(libs[lang]["crumb"])}</a>')
            more.append(f'<a class="btn btn-secondary" href="{rel(url_for(lang, libs[lang]["path"]))}">{esc(libs[lang]["crumb"])} →</a>')
    foot_html = f'  <nav class="foot-langs foot-hub" aria-label="{UI[lang]["guides"]}">\n    ' + "\n    ".join(foot) + "\n  </nav>"
    page = _put_block(page, FOOT_MARK, foot_html, '<p class="foot-made">')
    sec = re.search(r'<section class="guides wrap" id="guides">.*?</section>', page, re.S)
    if sec:
        more_html = ('  <div class="guide-actions" style="display:flex; flex-wrap:wrap; justify-content:center; gap:12px; margin-top:28px;">'
                     + "".join(more) + "</div>")
        new_sec = _put_block(sec.group(0), GUIDES_MARK, more_html, "</section>")
        page = page[:sec.start()] + new_sec + page[sec.end():]
    _home_cache[lang] = page
    return page


# ----------------------------------------------------------------------------- guides index (hub)

def render_hub(lang: str, guides: dict) -> str:
    h = HUB[lang]
    url = hub_url(lang)
    cards, items = [], []
    for slug, pages in guides.items():
        if lang not in pages or pages[lang][0].get("listed") == "no":
            continue
        m = pages[lang][0]
        u = url_for(lang, m["path"])
        cards.append(f'<a class="hub-card" href="{rel(u)}"><h2>{esc(m["h1"])}</h2><p>{esc(m["description"])}</p></a>')
        items.append(u)
    lib = CTX["library"].get(lang)
    if lib:
        u = url_for(lang, lib["path"])
        cards.insert(0, f'<a class="hub-card hub-stories" href="{rel(u)}"><h2>{esc(lib["h1"])}</h2><p>{esc(lib["description"])}</p></a>')
        items.insert(0, u)
    for src, (libs, _) in CTX["colls"].items():
        if src != "en" and lang in libs:
            u = url_for(lang, libs[lang]["path"])
            cards.insert(1, f'<a class="hub-card hub-stories" href="{rel(u)}"><h2>{esc(libs[lang]["h1"])}</h2><p>{esc(libs[lang]["description"])}</p></a>')
            items.insert(1, u)
    ld = [{"@type": "CollectionPage", "@id": url, "name": h["title"], "description": h["description"], "inLanguage": lang,
           "mainEntity": {"@type": "ItemList", "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": u} for i, u in enumerate(items)]}},
          {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Biblyx", "item": home_url(lang)},
              {"@type": "ListItem", "position": 2, "name": h["h1"], "item": url}]}]
    main = f"""<main class="wrap article hub">
  <article>
    <h1>{esc(h["h1"])}</h1>
    <p class="lede">{esc(h["intro"])}</p>
    <div class="hub-grid">
      {"\n      ".join(cards)}
    </div>
  </article>
</main>"""
    alternates = {l: hub_url(l) for l in LANGS}
    image = "/og-image.png" if lang == "en" else f"/og-image-{lang}.png"
    return page_shell(lang, title=h["title"], description=h["description"], url=url, alternates=alternates,
                      og_type="website", image=image, ld=ld, main=main)


# ----------------------------------------------------------------------------- story library

def load_stories(folder: str = "stories", src: str = "en"):
    """<folder>/library.json (texts per language) + <folder>/<slug>/story.json and <lang>.json.
    `src` is the language the stories are written in (en for stories/, de for stories-de/)."""
    sdir = ROOT / folder
    if not (sdir / "library.json").exists():
        return {}, {}
    library = json.loads((sdir / "library.json").read_text(encoding="utf-8"))
    order = library.pop("order")
    stories = {}
    for slug in order:
        d = sdir / slug
        story = json.loads((d / "story.json").read_text(encoding="utf-8"))
        story["slug"] = slug
        story["src"] = src
        story["folder"] = folder
        story["langs"] = {}
        for lang in LANGS:
            f = d / f"{lang}.json"
            if f.exists() and lang in library:
                loc = json.loads(f.read_text(encoding="utf-8"))
                loc["source_file"] = f
                loc["updated"] = git_date(f)
                story["langs"][lang] = loc
        stories[slug] = story
    for lang, lib in library.items():
        lib["folder"] = folder
        lib["source_file"] = sdir / "library.json"
        lib["updated"] = git_date(sdir / "library.json")
    return library, stories


# One collection per story language: CTX["colls"]["en"] = (library, stories) from stories/,
# CTX["colls"]["de"] from stories-de/ (German stories for Turkish readers). CTX["library"] and
# CTX["stories"] stay the English collection, which the nav, footer and home pages link to.
STORY_FOLDERS = {"en": "stories", "de": "stories-de"}


def libof(src_or_story, lang: str) -> dict:
    src = src_or_story if isinstance(src_or_story, str) else src_or_story["src"]
    return CTX["colls"][src][0][lang]


def story_url(lang: str, story: dict) -> str:
    return url_for(lang, f'{libof(story, lang)["path"]}/{story["langs"][lang]["path"]}')


def num(lang: str, n: int) -> str:
    s = f"{n:,}"
    if lang == "en":
        return s
    return s.replace(",", "\u00a0" if lang in ("fr", "pl", "ru") else ".")


def gloss_spans(story: dict):
    """Per paragraph: the sorted (start, end, gloss index) of each gloss, checked against the text."""
    spans = {}
    for k, g in enumerate(story["glosses"]):
        text = story["paragraphs"][g["p"]]
        hits = [m.span() for m in re.finditer(r"(?<![^\W\d_])" + re.escape(g["text"]) + r"(?![^\W\d_])", text)]
        if len(hits) < g.get("nth", 1):
            raise RuntimeError(f'{story["slug"]}: gloss {g["text"]!r} not found in paragraph {g["p"]}')
        a, b = hits[g.get("nth", 1) - 1]
        spans.setdefault(g["p"], []).append((a, b, k))
    for p, lst in spans.items():
        lst.sort()
        for (a1, b1, _), (a2, _, _) in zip(lst, lst[1:]):
            if a2 < b1:
                raise RuntimeError(f'{story["slug"]}: overlapping glosses in paragraph {p}')
    return spans


def story_paragraph(text: str, spans: list) -> str:
    out, pos = [], 0
    for a, b, k in spans:
        out.append(html.escape(text[pos:a], quote=False))
        out.append(f'<a class="g" href="#w{k}" data-k="{k}" role="button" aria-expanded="false">{html.escape(text[a:b], quote=False)}</a>')
        pos = b
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def gloss_rows(lang: str, story: dict):
    """(head, pos label, meaning, note, level) per gloss in this page's language."""
    lib = libof(story, lang)
    loc = story["langs"][lang].get("glosses")
    src = story["src"]
    rows = []
    for k, g in enumerate(story["glosses"]):
        if lang == src or not loc:
            m, note = g[src], g.get("note_" + src, "")
        else:
            m, note = loc[k]["m"], loc[k].get("note", "")
        rows.append(dict(w=g["head"], p=lib["pos"].get(g["pos"], g["pos"]), m=m, n=note, l=g["level"]))
    return rows


def play_link(campaign: str) -> str:
    return f"{PLAY}&referrer=utm_source%3Dbiblyx.com%26utm_medium%3Dwebsite%26utm_campaign%3D{campaign.replace('-', '_')}"


STORY_JS = """<script>
(function () {
  var data = JSON.parse(document.getElementById('gloss-data').textContent);
  var pop = document.createElement('div'), cur = null;
  pop.className = 'pop'; pop.setAttribute('role', 'dialog'); pop.hidden = true;
  document.body.appendChild(pop);
  function line(cls, text) { var s = document.createElement('span'); s.className = cls; s.textContent = text; pop.appendChild(s); return s; }
  function close() { if (cur) { cur.classList.remove('open'); cur.setAttribute('aria-expanded', 'false'); } cur = null; pop.hidden = true; }
  function open(a) {
    var d = data[+a.getAttribute('data-k')];
    pop.textContent = ''; line('w', d.w); line('m', d.m); if (d.n) line('note', d.n);
    var tags = line('tags', ''); [d.p, d.l].forEach(function (t) { var s = document.createElement('span'); s.textContent = t; tags.appendChild(s); });
    cur = a; a.classList.add('open'); a.setAttribute('aria-expanded', 'true'); pop.hidden = false;
    var r = a.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    var left = Math.max(8, Math.min(r.left, document.documentElement.clientWidth - w - 8));
    var top = r.bottom + 8; if (top + h > window.innerHeight - 8 && r.top - h - 8 > 8) top = r.top - h - 8;
    pop.style.left = (left + window.scrollX) + 'px'; pop.style.top = (top + window.scrollY) + 'px';
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a.g') : null;
    if (a) { e.preventDefault(); var same = a === cur; close(); if (!same) open(a); return; }
    if (!e.target.closest || !e.target.closest('.pop')) close();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  window.addEventListener('resize', close);
  function setTr(b, show) { var t = document.getElementById(b.getAttribute('aria-controls')); t.hidden = !show; b.setAttribute('aria-expanded', show ? 'true' : 'false'); }
  document.querySelectorAll('.tr-toggle').forEach(function (b) {
    b.addEventListener('click', function () { setTr(b, b.getAttribute('aria-expanded') !== 'true'); });
  });
  var all = document.getElementById('tr-all');
  if (all) all.addEventListener('click', function () {
    var show = all.getAttribute('aria-pressed') !== 'true';
    all.setAttribute('aria-pressed', show ? 'true' : 'false');
    document.querySelectorAll('.tr-toggle').forEach(function (b) { setTr(b, show); });
  });
})();
</script>"""


def is_own(story: dict) -> bool:
    return story.get("license") == "own"


def byline(lang: str, story: dict) -> str:
    """'Oscar Wilde · 1888' for public-domain texts, 'Brothers Grimm · retold in simple English' for our retellings."""
    if is_own(story):
        return f'{esc(story["author"])} · {esc(libof(story, lang)["retold"])}'
    return f'{esc(story["author"])} · {story["year"]}'


def level_band(story: dict) -> str:
    return re.split(r"[–-]", story["level"])[0].strip()


def chips(lang: str, story: dict) -> str:
    lib = libof(story, lang)
    return (f'<span class="chip level">{esc(story["level"])}</span>'
            f'<span class="chip">{esc(lib["minutes"].format(n=story["minutes"]))}</span>'
            f'<span class="chip">{esc(lib["words"].format(n=num(lang, story["words"])))}</span>'
            f'<span class="chip">{esc(lib["free"] if is_own(story) else lib["pd"])}</span>')


def render_story(lang: str, story: dict, stories: dict) -> str:
    lib = libof(story, lang)
    src = story["src"]
    loc = story["langs"][lang]
    url = story_url(lang, story)
    lib_url = url_for(lang, lib["path"])
    spans = gloss_spans(story)
    rows = gloss_rows(lang, story)
    tr = loc.get("translations") if lang != src else None
    paras, half = [], len(story["paragraphs"]) // 2
    play = play_link(f"story_{story['slug']}_{lang}")
    for i, text in enumerate(story["paragraphs"]):
        paras.append(f'<p class="en" id="p{i + 1}">{story_paragraph(text, spans.get(i, []))}</p>')
        if tr:
            paras.append(f'<button class="tr-toggle" type="button" lang="{lang}" aria-expanded="false" aria-controls="t{i + 1}">{esc(lib["toggle"])}</button>')
            paras.append(f'<p class="tr" id="t{i + 1}" lang="{lang}" hidden>{html.escape(tr[i], quote=False)}</p>')
        if i + 1 == half:
            paras.append(f'<div class="mid-cta" lang="{lang}"><p>{lib["mid"]}</p>'
                         f'<a class="btn btn-primary" href="{play}" target="_blank" rel="noopener">Google Play</a></div>')
    vocab = "".join(
        f'<tr id="w{k}"><td><span lang="{src}">{esc(r["w"])}</span> <small>{esc(r["p"])}</small></td>'
        f'<td>{esc(r["m"])}{f"<br><small>{esc(r["n"])}</small>" if r["n"] else ""}</td><td>{esc(r["l"])}</td></tr>'
        for k, r in enumerate(rows))
    cols = "".join(f"<th>{esc(c)}</th>" for c in lib["cols"])
    others = [s for s in stories.values() if s is not story and lang in s["langs"]]
    shelf = "".join(
        f'<a href="{rel(story_url(lang, s))}"><img src="{s["cover"]}" alt="" width="46" height="69" loading="lazy">'
        f'<span><span lang="{s["src"]}">{esc(s["title"])}</span><small>{esc(s["author"])} · {esc(s["level"])}</small></span></a>'
        for s in others)
    local = "" if lang == src else f' · <span>{esc(loc["local_title"])}</span>'
    if is_own(story):
        source = esc(lib["source_own"])
    else:
        source = lib["source"].format(link=f'<a href="{story["source"]}" rel="noopener">{esc(story["source_name"])}</a>')
    show_all = (f'<button class="show-all" id="tr-all" type="button" aria-pressed="false">{esc(lib["show_all"])}</button>'
                if tr else "")
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    main = f"""<main class="wrap article story-page">
  <article>
    <p class="crumbs"><a href="{rel(home_url(lang))}">Biblyx</a> › <a href="{rel(lib_url)}">{esc(lib["crumb"])}</a> › <span lang="{src}">{esc(story["title"])}</span></p>
    <header class="story-head">
      <img src="{story["cover"]}" alt="{esc(story["title"])}" width="120" height="180">
      <div>
        <h1 lang="{src}">{esc(story["title"])}</h1>
        <p class="author">{byline(lang, story)}{local}</p>
        <div class="chips">{chips(lang, story)}</div>
      </div>
    </header>
    <p class="lede">{esc(loc["intro"])}</p>
    <div class="howto"><p>{lib["howto"]}</p>{show_all}</div>
    <div class="story" lang="{src}">
{chr(10).join(paras)}
    </div>
    <p class="source">{source}</p>
    <p class="epub"><a class="btn btn-ghost" href="{epub_path(story)}" download>{esc(lib["epub_btn"])}</a> <small>{esc(lib["epub_hint"])}</small></p>
    <section class="vocab">
      <h2>{esc(lib["vocab"])}</h2>
      <div class="table-wrap"><table><thead><tr>{cols}</tr></thead><tbody>{vocab}</tbody></table></div>
    </section>
  </article>
  <aside class="cta">
    <h2>{UI[lang]["cta"]}</h2>
    <p>{esc(lib["cta_line"].format(slogan=SLOGAN[lang]))}</p>
    <a class="btn btn-primary" href="{play}" target="_blank" rel="noopener">{UI[lang]["button"]}</a>
  </aside>
  <aside class="also">
    <h2>{esc(lib["shelf"])}</h2>
    <div class="shelf">{shelf}</div>
  </aside>
</main>
<script type="application/json" id="gloss-data">{data}</script>"""
    alternates = {l: story_url(l, story) for l in story["langs"]}
    ld = [{"@type": "WebPage", "@id": url, "name": loc["title"], "description": loc["description"], "inLanguage": lang,
           "isPartOf": {"@type": "CollectionPage", "@id": lib_url},
           "mainEntity": {"@type": "CreativeWork", "name": story["title"], "inLanguage": src,
                          "author": ({"@type": "Organization", "name": "Biblyx"} if is_own(story)
                                     else {"@type": "Person", "name": story["author"]}),
                          "datePublished": str(story["year"]),
                          **({} if is_own(story) else {"license": "https://creativecommons.org/publicdomain/mark/1.0/",
                                                        "isBasedOn": story["source"]}),
                          "image": SITE + story["cover"]}},
          {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Biblyx", "item": home_url(lang)},
              {"@type": "ListItem", "position": 2, "name": lib["crumb"], "item": lib_url},
              {"@type": "ListItem", "position": 3, "name": story["title"], "item": url}]}]
    image = "/og-image.png" if lang == "en" else f"/og-image-{lang}.png"
    return page_shell(lang, title=loc["title"], description=loc["description"], url=url, alternates=alternates,
                      og_type="article", image=image, ld=ld, main=main, scripts=STORY_JS)


def render_library(lang: str, stories: dict, src: str = "en") -> str:
    lib = libof(src, lang)
    url = url_for(lang, lib["path"])
    cards, bands = [], []
    ordered = sorted((s for s in stories.values() if lang in s["langs"]),
                     key=lambda s: ["A1", "A2", "B1", "B2", "C1"].index(level_band(s)))
    for s in ordered:
        band = level_band(s)
        if band not in bands:
            bands.append(band)
            cards.append(f'<h2 class="level-head" id="{band.lower()}">{esc(lib["level_head"].format(lv=band))}</h2>')
        loc = s["langs"][lang]
        local = "" if lang == src else f' · {esc(loc["local_title"])}'
        cards.append(f"""<article class="story-card">
      <a href="{rel(story_url(lang, s))}"><img src="{s["cover"]}" alt="{esc(s["title"])}" width="120" height="180" loading="lazy"></a>
      <div>
        <h2><a href="{rel(story_url(lang, s))}" lang="{src}">{esc(s["title"])}</a></h2>
        <p class="author">{byline(lang, s)}{local}</p>
        <div class="chips">{chips(lang, s)}</div>
        <p>{esc(loc["intro"])}</p>
        <a class="more" href="{rel(story_url(lang, s))}">{esc(lib["read"])}</a>
      </div>
    </article>""")
    play = play_link(f"stories_{lang}" if src == "en" else f"stories_{src}_{lang}")
    main = f"""<main class="wrap article library">
  <article>
    <p class="crumbs"><a href="{rel(home_url(lang))}">Biblyx</a> › {esc(lib["crumb"])}</p>
    <h1>{esc(lib["h1"])}</h1>
    <p class="lede">{esc(lib["intro"])}</p>
    <div class="howto"><p>{lib["howto"]}</p></div>
    <nav class="level-nav" aria-label="{esc(lib["level_head"].format(lv=""))}">{"".join(f'<a class="chip level" href="#{b.lower()}">{b}</a>' for b in bands)}</nav>
    {"\n    ".join(cards)}
  </article>
  <aside class="cta">
    <h2>{UI[lang]["cta"]}</h2>
    <p>{esc(lib["cta_line"].format(slogan=SLOGAN[lang]))}</p>
    <a class="btn btn-primary" href="{play}" target="_blank" rel="noopener">{UI[lang]["button"]}</a>
  </aside>
</main>"""
    alternates = {l: url_for(l, libof(src, l)["path"]) for l in CTX["colls"][src][0]}
    ld = [{"@type": "CollectionPage", "@id": url, "name": lib["title"], "description": lib["description"], "inLanguage": lang,
           "mainEntity": {"@type": "ItemList", "itemListElement": [
               {"@type": "ListItem", "position": i + 1, "url": story_url(lang, s)}
               for i, s in enumerate(x for x in stories.values() if lang in x["langs"])]}},
          {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Biblyx", "item": home_url(lang)},
              {"@type": "ListItem", "position": 2, "name": lib["crumb"], "item": url}]}]
    image = "/og-image.png" if lang == "en" else f"/og-image-{lang}.png"
    return page_shell(lang, title=lib["title"], description=lib["description"], url=url, alternates=alternates,
                      og_type="website", image=image, ld=ld, main=main)


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
    hubs = {l: hub_url(l) for l in LANGS}
    for l in LANGS:
        dates = [m["updated"] for p in guides.values() for ll, (m, _) in p.items() if ll == l] or [dt.date.today().isoformat()]
        blocks.append(url_block(hubs[l], max(dates), hubs, hubs["en"]))
    for lib, stories in CTX["colls"].values():
        if not lib:
            continue
        libs = {l: url_for(l, lib[l]["path"]) for l in lib}
        for l in lib:
            blocks.append(url_block(libs[l], lib[l]["updated"], libs, libs.get("en", libs[sorted(libs)[0]])))
        for story in stories.values():
            alts = {l: story_url(l, story) for l in story["langs"]}
            for l, loc in story["langs"].items():
                blocks.append(url_block(alts[l], loc["updated"], alts, alts.get("en", alts[sorted(alts)[0]])))
    for page in ("privacy-policy", "terms", "account-deletion"):
        blocks.append(f"  <url>\n    <loc>{SITE}/{page}</loc>\n    <lastmod>{git_date(ROOT / (page + '.html'))}</lastmod>\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(blocks) + "\n</urlset>\n")


# ----------------------------------------------------------------------------- checks

def check_page(lang: str, meta: dict, page: str, warnings: list):
    where = f"{meta['source'].relative_to(ROOT)}"
    check_html(where, page, meta["title"], meta["description"], warnings)
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


def check_html(where: str, page: str, title: str, description: str, warnings: list):
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
    if len(title) > 60:
        warnings.append(f"{where}: title is {len(title)} characters (keep ≤ 60)")
    if not 110 <= len(description) <= 165:
        warnings.append(f"{where}: description is {len(description)} characters (aim 120–160)")


# ---------------------------------------------------------------------------
# EPUB per story: English text only, opens in Biblyx (or any e-reader).
# Deterministic bytes (fixed zip timestamps) so a rebuild does not churn git.

EPUB_TEXT = {
    "en": dict(end=("Learn languages by reading your own books.",
                    "More free English stories: https://biblyx.com/english-short-stories/"),
               own="Retold in simple English by Biblyx.", pd="Text: {src} ({year}), public domain.", level="Level"),
    "de": dict(end=("Sprachen lernen beim Lesen deiner eigenen Bücher.",
                    "Weitere kostenlose deutsche Geschichten: https://biblyx.com/tr/almanca-hikayeler/"),
               own="In einfachem Deutsch nacherzählt von Biblyx.", pd="Text: {src} ({year}), gemeinfrei.", level="Niveau"),
}


def epub_path(story: dict) -> str:
    return f'/assets/stories/{story["slug"]}.epub'


def build_epub(story: dict) -> bytes:
    import io
    x = lambda t: html.escape(t, quote=True)
    slug, title, author = story["slug"], story["title"], story["author"]
    src = story["src"]
    T = EPUB_TEXT[src]
    uid = f"https://biblyx.com{epub_path(story)}"
    note = T["own"] if is_own(story) else T["pd"].format(src=story.get("source_name", ""), year=story["year"])
    cover = (ROOT / story["cover"].lstrip("/")).read_bytes()
    paras = "\n".join(f"<p>{x(t)}</p>" for t in story["paragraphs"])
    head = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{src}" lang="{src}">')
    text = (f'{head}<head><meta charset="utf-8"/><title>{x(title)}</title>'
            '<style>body{font-family:serif;line-height:1.5} h1{text-align:center} .by{text-align:center;font-style:italic}'
            ' .end{margin-top:2em;font-size:.9em;text-align:center}</style></head><body>'
            f'<section epub:type="chapter"><h1>{x(title)}</h1><p class="by">{x(author)} · {T["level"]} {x(story["level"])}</p>'
            f'{paras}<p class="end">{x(note)}<br/>{x(T["end"][0])}<br/>{x(T["end"][1])}</p></section></body></html>')
    nav = (f'{head}<head><meta charset="utf-8"/><title>{x(title)}</title></head><body>'
           f'<nav epub:type="toc" id="toc"><ol><li><a href="text.xhtml">{x(title)}</a></li></ol></nav></body></html>')
    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{x(uid)}"/></head><docTitle><text>{x(title)}</text></docTitle>'
           f'<navMap><navPoint id="n1" playOrder="1"><navLabel><text>{x(title)}</text></navLabel>'
           '<content src="text.xhtml"/></navPoint></navMap></ncx>')
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="{src}">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="uid">{x(uid)}</dc:identifier><dc:title>{x(title)}</dc:title>'
           f'<dc:creator>{x(author)}</dc:creator><dc:language>{src}</dc:language><dc:publisher>Biblyx</dc:publisher>'
           f'<dc:description>{x(note)}</dc:description><meta name="cover" content="cover"/>'
           '<meta property="dcterms:modified">2026-11-11T00:00:00Z</meta></metadata>'
           '<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
           '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
           '<item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>'
           '<item id="text" href="text.xhtml" media-type="application/xhtml+xml"/></manifest>'
           '<spine toc="ncx"><itemref idref="text"/></spine></package>')
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        def put(name, data, deflate=True):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED if deflate else zipfile.ZIP_STORED
            z.writestr(info, data)
        put("mimetype", "application/epub+zip", deflate=False)
        put("META-INF/container.xml", container)
        put("OEBPS/content.opf", opf)
        put("OEBPS/nav.xhtml", nav)
        put("OEBPS/toc.ncx", ncx)
        put("OEBPS/text.xhtml", text)
        put("OEBPS/cover.jpg", cover, deflate=False)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write into this directory instead of the repo")
    ap.add_argument("--check", action="store_true", help="build in memory and report checks only")
    ap.add_argument("--drafts", action="store_true", help="include guides/_*/ folders")
    args = ap.parse_args()
    out_root = Path(args.out).resolve() if args.out else ROOT
    guides = load_guides(args.drafts)
    CTX["colls"] = {src: load_stories(folder, src) for src, folder in STORY_FOLDERS.items()}
    CTX["library"], CTX["stories"] = CTX["colls"]["en"]
    CTX["guides"] = guides
    warnings, written = [], []

    def emit(url: str, page: str):
        target_rel = Path(url.replace(SITE + "/", "")) / "index.html"
        if not args.check:
            target = out_root / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(page, encoding="utf-8")
            written.append(str(target_rel))

    for slug, pages in guides.items():
        for lang, (meta, body) in pages.items():
            page = render_guide(slug, lang, meta, body, pages, guides)
            check_page(lang, meta, page, warnings)
            emit(url_for(lang, meta["path"]), page)
    for lang in LANGS:
        page = render_hub(lang, guides)
        check_html(f"hub:{lang}", page, HUB[lang]["title"], HUB[lang]["description"], warnings)
        emit(hub_url(lang), page)
    for src, (libs, stories) in CTX["colls"].items():
      for lang, lib in libs.items():
        page = render_library(lang, stories, src)
        check_html(f"{lib['folder']}/library.json:{lang}", page, lib["title"], lib["description"], warnings)
        emit(url_for(lang, lib["path"]), page)
        for story in stories.values():
            if lang in story["langs"]:
                loc = story["langs"][lang]
                page = render_story(lang, story, stories)
                check_html(str(loc["source_file"].relative_to(ROOT)), page, loc["title"], loc["description"], warnings)
                if page.count(SLOGAN[lang]) != 1:
                    warnings.append(f"{story['slug']}/{lang}: the slogan appears {page.count(SLOGAN[lang])} times (expected once)")
                emit(story_url(lang, story), page)
    for story in (s for _, sts in CTX["colls"].values() for s in sts.values()):
        data = build_epub(story)
        target = out_root / epub_path(story).lstrip("/")
        if not args.check and (not target.exists() or target.read_bytes() != data):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written.append(epub_path(story).lstrip("/"))
    for lang in LANGS:
        page = home_with_rows(lang)
        if page != home_page(lang) and not args.check:
            target_rel = Path("index.html" if lang == "en" else f"{lang}/index.html")
            (out_root / target_rel).parent.mkdir(parents=True, exist_ok=True)
            (out_root / target_rel).write_text(page, encoding="utf-8")
            written.append(str(target_rel))
    urls = set()
    for w in written:
        if w in urls:
            warnings.append(f"{w}: written twice (two pages share a path) don't balance")
        urls.add(w)
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
