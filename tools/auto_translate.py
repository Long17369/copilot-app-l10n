"""auto_translate.py - compositionally translate UI strings using the existing dictionary.

Instead of hand-writing every remaining string, treat the merged dictionary as a phrase
table and translate a new string by splitting it into known pieces:

    "Add a label"      -> 添加 + 标签            -> 添加标签
    "Session settings" -> 会话 + 设置            -> 会话设置
    "No pull requests" -> 无 + 拉取请求          -> 无拉取请求

Only *fully covered* strings are emitted: if any word is unknown the string is skipped,
so the output never contains half-English results. This keeps the script useful at scale
without needing a network translation service.

    python tools/auto_translate.py                # report coverage, write candidates
    python tools/auto_translate.py --write        # also write i18n/zz-auto.extra.json
    python tools/auto_translate.py --show 60      # print sample translations
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import apply_zh  # noqa: E402

STRINGS = os.path.join(ROOT, "build", "ui-strings.txt")
OUT_JSON = os.path.join(ROOT, "build", "auto-candidates.json")
OUT_DICT = os.path.join(ROOT, "i18n", "zz-auto.extra.json")

# Words that may be dropped or need no rendering in Chinese.
DROP = {"a", "an", "the", "to", "of", "for", "in", "on", "at", "by", "with", "and"}
# Sentence-final punctuation handled separately.
PUNCT = {".", "。", "!", "！", "?", "？", ":", "："}

# Fixed renderings for grammatical glue that appears in composed labels.
GLUE = {
    "a": "", "an": "", "the": "",
    "and": "和", "or": "或", "with": "，带", "without": "无",
    "for": "：", "from": "来自", "to": "至", "in": "在", "on": "在",
    "of": "的", "by": "由", "as": "作为", "at": "在",
    "not": "不", "no": "无", "any": "任意", "all": "所有", "each": "每个",
    "more": "更多", "less": "更少", "new": "新建", "up": "上", "down": "下",
}

MAX_WORDS = 9


def load_strings(path: str):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            count, _, text = line.rstrip("\n").partition("\t")
            if not text:
                continue
            rows.append((int(count), text))
    return rows


def build_phrase_table(dictionary: dict) -> dict:
    """Lower-cased phrase -> Chinese, longest phrases first at match time."""
    table = {}
    for en, zh in dictionary.items():
        key = en.strip().lower()
        if not key or len(key) > 60:
            continue
        # Skip entries that are whole sentences; they would swallow smaller phrases.
        if len(key.split()) > 6:
            continue
        table.setdefault(key, zh)
    return table


def tokenize_prepared(text: str):
    """Split into words plus separators (punctuation, dashes) for reassembly."""
    return re.findall(r"[A-Za-z][A-Za-z'’-]*|\d+|[^\sA-Za-z\d]+", text)


def match_phrase(words, start, table, max_len):
    """Longest dictionary match starting at `start`. Returns (length, chinese) or None."""
    for size in range(min(max_len, len(words) - start), 0, -1):
        candidate = " ".join(words[start:start + size]).lower()
        if candidate in table:
            return size, table[candidate]
    return None


def translate_compositional(text: str, table: dict, dictionary: dict):
    """Return a Chinese rendering, or None when any part is unknown."""
    body = text.strip()
    trailing = ""
    while body and body[-1] in PUNCT:
        trailing = body[-1] + trailing
        body = body[:-1].rstrip()
    if trailing:
        trailing = {'.': '。', '!': '！', '?': '？', ':': '：'}.get(
            trailing[0], trailing[0])
    if not body:
        return None

    # Exact match first (case-insensitive), keeps existing wording stable.
    if body.lower() in table:
        value = table[body.lower()]
        return value + trailing

    words = body.split()
    if len(words) > MAX_WORDS:
        return None

    pieces = []
    index = 0
    matched = 0
    while index < len(words):
        hit = match_phrase(words, index, table, 4)
        if hit:
            size, chinese = hit
            pieces.append(chinese)
            index += size
            matched += size
            continue
        word = words[index]
        low = word.lower().strip(",:;()")
        if low in DROP:
            index += 1
            matched += 1
            continue
        if low in GLUE:
            pieces.append(GLUE[low])
            index += 1
            matched += 1
            continue
        return None  # unknown word: refuse to emit a half-translated string

    if matched < len(words):
        return None
    result = "".join(pieces)
    result = re.sub(r"\s+", "", result)
    result = re.sub(r"^[，：]+", "", result)
    return result + trailing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--show", type=int, default=40)
    args = parser.parse_args()

    dictionary = apply_zh.load_dictionary()
    table = build_phrase_table(dictionary)
    print("dictionary: %d entries (%d phrase-table keys)" % (len(dictionary), len(table)))

    rows = load_strings(STRINGS)
    print("candidate strings: %d" % len(rows))

    translated = {}
    skipped = []
    for _count, text in rows:
        if text in dictionary:
            continue
        if not re.search(r"[A-Za-z]", text):
            continue
        value = translate_compositional(text, table, dictionary)
        if value is None:
            skipped.append(text)
        elif value != text:
            translated[text] = value

    print("compositional hits: %d" % len(translated))
    print("still uncovered   : %d" % len(skipped))

    params = [(len(apply_zh.load_dictionary()) + len(translated), len(rows))]
    if params:
        after = params[0][0]
        print("coverage after merge: %d/%d (%.1f%%)"
              % (after, len(rows), 100.0 * after / max(1, len(rows))))

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(translated, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print("candidates -> %s" % OUT_JSON)

    for en, zh in list(translated.items())[: args.show]:
        print("  %-52s %s" % (en[:50], zh))

    if args.write:
        with open(OUT_DICT, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(translated, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print("dictionary shard -> %s" % OUT_DICT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
