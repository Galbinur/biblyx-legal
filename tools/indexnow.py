#!/usr/bin/env python3
"""Tell IndexNow which biblyx.com pages changed (Bing, Yandex, Naver, Seznam share one
submission; Google ignores IndexNow and reads the sitemap instead).

    python3 tools/indexnow.py --since <git-rev> [--dry-run]     # pages whose .html changed since that commit
    python3 tools/indexnow.py https://biblyx.com/ https://biblyx.com/tr/ [--dry-run]

The key is public by design: the engine verifies it by fetching https://biblyx.com/<key>.txt,
so <key>.txt lives in the repo root (32 hex characters, content = file name). Run it after the
push is live, never before: the engine fetches the URLs within minutes. 200 and 202 mean accepted.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://biblyx.com"
ENDPOINT = "https://www.bing.com/indexnow"


def key() -> str:
    for p in ROOT.glob("*.txt"):
        k = p.read_text(encoding="utf-8").strip()
        if k == p.stem and len(k) == 32 and all(c in "0123456789abcdef" for c in k):
            return k
    sys.exit("no IndexNow key file (<32 hex>.txt with the key as content) in the repo root")


def url_of(rel: str):
    if not rel.endswith(".html"):
        return None
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[:-len('index.html')]}"
    return f"{SITE}/{rel[:-len('.html')]}"


def changed_since(rev: str) -> list:
    out = subprocess.run(["git", "diff", "--name-only", f"{rev}..HEAD", "--"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    urls = sorted({u for u in (url_of(r) for r in out) if u and (ROOT / r).exists()})
    return urls


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if args[:1] == ["--since"]:
        urls = changed_since(args[1])
    else:
        urls = args
    if not urls:
        print("nothing to submit")
        return
    k = key()
    body = {"host": "biblyx.com", "key": k, "keyLocation": f"{SITE}/{k}.txt", "urlList": urls}
    print(f"{len(urls)} URL(s):", *urls, sep="\n  ")
    if dry:
        return
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("IndexNow:", r.status, "accepted" if r.status in (200, 202) else r.reason)
    except urllib.error.HTTPError as e:
        sys.exit(f"IndexNow refused: {e.code} {e.reason} {e.read()[:200]!r}")


if __name__ == "__main__":
    main()
