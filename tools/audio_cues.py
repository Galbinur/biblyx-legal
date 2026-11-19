#!/usr/bin/env python3
"""Writes stories*/<slug>/audio.json from the narration repo (biblyx-audio).

  python3 tools/audio_cues.py ../biblyx-audio

For each story with narration: the MP3 URL on audio.biblyx.com, its length,
and the cues [start second, paragraph index] that tell the story page which
paragraph is being read. The narration's timing.json indexes characters of
"title.\\n" + the book's paragraphs; the site may split a long paragraph in
two, so every site paragraph is located in that text and each timed sentence
is given to the paragraph it starts in (-1 = title or the closing lines).
Run it again only when the narration changes."""
import json, os, sys

BASE = "https://audio.biblyx.com"
MAP = {
    "stories": {
        "the-selfish-giant": "en/en_selfish_giant", "the-gift-of-the-magi": "en/en_gift_of_the_magi",
        "the-tell-tale-heart": "en/en_tell_tale_heart", "little-red-riding-hood": "en/en_little_red_riding_hood",
        "the-three-little-pigs": "en/en_three_little_pigs", "the-ugly-duckling": "en/en_ugly_duckling",
        "goldilocks-and-the-three-bears": "en/en_goldilocks", "rapunzel": "en/en_rapunzel", "pinocchio": "en/en_pinocchio"},
    "stories-de": {
        "der-hase-und-der-igel": "de/de_hase_igel", "der-wolf-und-die-sieben-jungen-geisslein": "de/de_wolf_sieben_geisslein",
        "die-bremer-stadtmusikanten": "de/de_bremer_stadtmusikanten", "haensel-und-gretel": "de/de_haensel_gretel",
        "rotkaeppchen": "de/de_rotkaeppchen", "vor-dem-gesetz": "de/de_vor_dem_gesetz"},
}


def main(audio_root: str) -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for folder, stories in MAP.items():
        for slug, af in stories.items():
            story = json.load(open(os.path.join(here, folder, slug, "story.json"), encoding="utf-8"))
            timing = json.load(open(os.path.join(audio_root, af, "timing.json"), encoding="utf-8"))
            if len(timing["files"]) != 1:
                sys.exit(f"{slug}: {len(timing['files'])} audio parts; the page player plays one file")
            text, spans, pos = timing["text"], [], 0
            for i, p in enumerate(story["paragraphs"]):
                k = text.find(p, pos)
                if k < 0:
                    sys.exit(f"{slug}: paragraph {i + 1} not found in the narration text")
                spans.append((k, k + len(p)))
                pos = k + len(p)
            cues, last = [], None
            for s in timing["sentences"]:
                para = next((i for i, (a, b) in enumerate(spans) if a <= s["start"] < b), -1)
                if para != last:
                    cues.append([round(float(s["start_s"]), 2), para])
                    last = para
            f = timing["files"][0]
            out = {"src": f"{BASE}/{af}/{f['file']}", "duration": round(float(timing["duration_s"]), 1),
                   "bytes": f["bytes"], "cues": cues}
            path = os.path.join(here, folder, slug, "audio.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"{folder}/{slug}: {len(cues)} cues, {out['duration']} s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../biblyx-audio")
