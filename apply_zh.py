#!/usr/bin/env python3
"""apply_zh.py - inject the Simplified-Chinese runtime localizer into the Copilot app.

It builds ``build/zh-cn.payload.js`` from ``i18n/zh-cn.engine.js`` +
``i18n/zh-cn.dict.json`` and appends it to a startup chunk of the application, then
switches ``index.html`` to ``<html lang="zh-CN">``.

Examples
--------
    # patch a copy first (safe while the app is running)
    python apply_zh.py --copy C:\\temp\\github-zh.exe

    # apply to the installed app (close the app first)
    python apply_zh.py

    # preview sizes without writing anything
    python apply_zh.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import copilot_l10n as l10n

ROOT = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(ROOT, "i18n", "zh-cn.engine.js")
I18N_DIR = os.path.join(ROOT, "i18n")
DICT = os.path.join(I18N_DIR, "zh-cn.dict.json")
BUILD = os.path.join(ROOT, "build")

DEFAULT_ASSET = "auto"
MIN_SLACK = 1024

BOOT_MARKER = "/*__COPILOT_L10N_BOOT__*/"

# Asset names carry a content hash that changes on every app update, so patterns are
# matched on the stable prefix instead of the full name.
CANDIDATE_PREFIXES = (
    "/assets/useWebSocketTransport-",
    "/assets/App-",
    "/assets/router-",
    "/assets/ExtensionsView-",
    "/assets/switch-",
    "/assets/PullRequestDetailView-",
    "/assets/vendor-terminal-",
)
ENTRY_PREFIXES = ("/assets/index-",)


def _paths_with_prefix(af, prefixes, limit=40):
    """Collect embedded asset paths whose name starts with one of `prefixes`.

    Only the path strings are searched the first time; each hit is then validated through
    the descriptor table, so a stale string in the binary cannot be used.
    """
    found = []
    for prefix in prefixes:
        needle = prefix.encode("latin1")
        start = 0
        while len(found) < limit:
            pos = af.data.find(needle, start)
            if pos == -1:
                break
            start = pos + 1
            end = pos
            while end < len(af.data):
                ch = af.data[end]
                if not (48 <= ch <= 57 or 65 <= ch <= 90 or 97 <= ch <= 122
                        or ch in (0x2E, 0x2D, 0x5F, 0x2F)):  # . - _ /
                    break
                end += 1
            path = bytes(af.data[pos:end]).decode("latin1")
            if not path.endswith(".js"):
                continue
            try:
                info = af.locate(path)
            except LookupError:
                continue
            if len(info["raw"]) < 1024:
                continue
            if path not in [p for p, _ in found]:
                found.append((path, info))
    return found


_DISCOVER_CACHE = {}


def baseline_source(exe: str) -> str:
    """Path to read pristine bytes from: the backup only when it matches this build."""
    bak = l10n.backup_path(exe)
    try:
        if os.path.exists(bak) and os.path.getsize(bak) == os.path.getsize(exe):
            return bak
    except OSError:
        pass
    return exe


def discover_assets(exe: str):
    """Return (candidates, entry) for the current build.

    Candidates are ordered by available headroom; the entry chunk is the one loaded by
    index.html, identified by its small size and index- prefix. Results are cached per
    file revision because the pipeline asks several times.
    """
    source = baseline_source(exe)
    try:
        stat = os.stat(source)
        key = (source, stat.st_size, stat.st_mtime_ns)
    except OSError:
        key = None
    if key is not None and key in _DISCOVER_CACHE:
        return _DISCOVER_CACHE[key]

    with l10n.AssetFile(source) as af:
        candidates = _paths_with_prefix(af, CANDIDATE_PREFIXES)
        entries = _paths_with_prefix(af, ENTRY_PREFIXES, limit=10)

    if not candidates:
        raise ValueError(
            "no startup chunks found in %s; is this a supported Copilot build?"
            % source
        )

    # The entry chunk is the index-*.js that index.html imports; pick the one whose size
    # looks like an entry module, falling back to the smallest index- chunk.
    entry = None
    for path, info in sorted(entries, key=lambda kv: len(kv[1]["raw"])):
        if 20000 <= len(info["raw"]) <= 60000:
            entry = path
            break
    if entry is None and entries:
        entry = sorted(entries, key=lambda kv: len(kv[1]["raw"]))[0][0]

    candidates.sort(key=lambda kv: -kv[1]["br_len"])
    l10n.log("discovered %d candidate chunk(s), entry %s"
             % (len(candidates), entry))
    result = (candidates, entry)
    if key is not None:
        _DISCOVER_CACHE[key] = result
    return result


STATE_FILE = os.path.join(BUILD, "last-chunk.json")


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        os.makedirs(BUILD, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except OSError:
        pass


def _remember(exe: str, asset: str) -> None:
    import hashlib

    state = _load_state()
    state[exe] = {
        "asset": asset,
        "payload_sha": hashlib.sha1(build_payload()).hexdigest(),
        "exe_size": os.path.getsize(exe),
    }
    _save_state(state)


def is_current(exe: str, asset: str) -> bool:
    """True when the executable already carries exactly this payload and wiring."""
    import hashlib

    state = _load_state()
    entry = state.get(exe)
    if not isinstance(entry, dict):
        return False
    if entry.get("payload_sha") != hashlib.sha1(build_payload()).hexdigest():
        return False
    if entry.get("exe_size") != os.path.getsize(exe):
        return False
    chunk = entry.get("asset")
    candidates, entry_asset = discover_assets(exe)
    if chunk not in [p for p, _ in candidates]:
        return False
    with l10n.AssetFile(exe) as af:
        try:
            if l10n.MARKER.encode() not in af.locate(chunk)["raw"]:
                return False
            if b'lang="zh-CN"' not in af.locate("index.html")["raw"]:
                return False
            if chunk != entry_asset and entry_asset and \
                    BOOT_MARKER.encode() not in af.locate(entry_asset)["raw"]:
                return False
        except (LookupError, KeyError):
            return False
    return True


def pick_asset(exe: str, payload: bytes) -> str:
    """Return the startup chunk to patch.

    A previously successful choice is reused without re-measuring (the caller falls back
    to a fresh scan if it no longer fits). Otherwise candidates are tried biggest-first:
    headroom scales with chunk size, so the first attempt almost always wins.
    """
    found, _entry = discover_assets(exe)
    available = [p for p, _ in found]

    state = _load_state()
    remembered = state.get(exe)
    if isinstance(remembered, dict):
        remembered = remembered.get("asset")
    if remembered in available:
        l10n.log("reusing previously chosen chunk: %s" % remembered)
        return remembered

    defects = []
    for candidate, info in found:
        l10n.log("measuring %s (%.1f MB)" % (candidate, len(info["raw"]) / 1e6))
        with l10n.heartbeat("  compressing"):
            packed, quality = l10n.compress_fitting(
                info["raw"] + b"\n" + payload + b"\n", info["br_len"] - MIN_SLACK)
        slack = info["br_len"] - len(packed)
        if slack >= MIN_SLACK:
            l10n.log("chosen chunk: %s (slack %d bytes, quality %d)"
                     % (candidate, slack, quality))
            _remember(exe, candidate)
            return candidate
        defects.append("%s: slack %d < %d" % (candidate, slack, MIN_SLACK))
    raise ValueError(
        "no startup chunk has room for the payload:\n  " + "\n  ".join(defects) +
        "\nPick another chunk with `copilot_l10n.py list App-` and pass --asset."
    )


def bootstrap_transform(assets):
    """Append static imports of `assets` to the entry chunk."""
    specs = ["./" + a.rsplit("/", 1)[-1] for a in assets]

    def transform(raw: bytes) -> bytes:
        text = raw.decode("utf-8")
        if BOOT_MARKER in text:
            return raw
        body = "\n" + BOOT_MARKER + "".join(
            'import("%s").catch(function(){});\n' % spec for spec in specs
        )
        return (text + body).encode("utf-8")

    return transform


TERMINOLOGY_PATH = os.path.join(I18N_DIR, "terminology.json")


def load_terminology() -> dict:
    try:
        with open(TERMINOLOGY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    data.setdefault("keep_english", [])
    data.setdefault("rewrite", [])
    data.setdefault("keep_english_keys", [])
    data.setdefault("overrides", {})
    return data


CJK_LATIN = re.compile(r"([\u4e00-\u9fff])([A-Za-z0-9])")
LATIN_CJK = re.compile(r"([A-Za-z0-9])([\u4e00-\u9fff])")


def normalize_spacing(text: str) -> str:
    """Put a space between Chinese and Latin/digits, as Chinese typography expects."""
    out = CJK_LATIN.sub(r"\1 \2", text)
    out = LATIN_CJK.sub(r"\1 \2", out)
    return re.sub(r" {2,}", " ", out)


def apply_terminology(dictionary: dict, term: dict) -> dict:
    """Enforce the terminology policy on a merged dictionary.

    Order matters: exact overrides win, then terms that must stay English are removed,
    then Chinese renderings are rewritten inside the remaining sentences.
    """
    keep_keys = {k.strip().lower() for k in term["keep_english_keys"]}
    keep_words = {w.strip().lower() for w in term["keep_english"]}

    out = {}
    pinned = set(term["overrides"])
    for en, zh in dictionary.items():
        if en in term["overrides"]:
            out[en] = normalize_spacing(term["overrides"][en])
            continue
        # A bare term that must stay English is dropped so the source text is used.
        if en.strip().lower() in keep_words:
            continue
        if en.strip().lower() in keep_keys:
            continue
        out[en] = zh

    for en, zh in list(out.items()):
        if en in pinned:
            continue
        value = zh
        for rule in term["rewrite"]:
            if not isinstance(rule, dict):
                continue
            source = rule.get("from")
            target = rule.get("to")
            if not source or not target or source not in value:
                continue
            skip = rule.get("skip_if_contains") or []
            if any(token in value for token in skip):
                continue
            value = value.replace(source, target)
        value = normalize_spacing(value)
        if value != zh:
            out[en] = value
    return out


def _fragment_order(name: str):
    """Deterministic merge order: numeric, with zz-* corrections applied last.

    Plain alphabetical sorting put ``ui2`` after ``ui15``, so an older fragment could
    silently override a newer translation.
    """
    if name.startswith("zz-"):
        return (2, 0, name)
    digits = re.findall(r"\d+", name)
    if digits:
        return (1, int(digits[-1]), name)
    return (0, 0, name)


def load_dictionary() -> dict:
    """Merge every dictionary fragment in i18n/, base dictionary first.

    ``zh-cn.dict.json`` is the core list; additional ``*.extra.json`` fragments are
    layered on top (later files win), which keeps incremental additions reviewable.
    ``zz-*.extra.json`` files always win, so corrections are never shadowed.
    The terminology policy is applied last.
    """
    files = ["zh-cn.dict.json"]
    files += sorted(
        (name for name in os.listdir(I18N_DIR)
         if name.endswith(".extra.json")),
        key=_fragment_order,
    )
    merged = {}
    for name in files:
        path = os.path.join(I18N_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            merged.update(json.load(fh))
    return apply_terminology(merged, load_terminology())


def build_dictionary_parts(max_bytes: int = 30000):
    """Split the merged dictionary into shards of roughly `max_bytes` of JSON."""
    dictionary = load_dictionary()
    parts, current, size = [], {}, 0
    for en, zh in dictionary.items():
        item = json.dumps({en: zh}, ensure_ascii=False)[1:-1]
        if current and size + len(item) > max_bytes:
            parts.append(current)
            current, size = {}, 0
        current[en] = zh
        size += len(item)
    if current:
        parts.append(current)
    return parts


def build_shard_scripts(max_bytes: int = 30000):
    """Return JS snippets: the first carries the engine, the rest only add dictionary shards.

    Each snippet registers its share through globals so the engine can wait until every
    shard has been evaluated before it starts translating.
    """
    with open(ENGINE, "r", encoding="utf-8") as fh:
        engine = fh.read()
    term = load_terminology()
    parts = build_dictionary_parts(max_bytes)

    for placeholder in ("__KEEP_JSON__", "__EXPECT__"):
        if placeholder not in engine:
            raise ValueError("engine is missing the %s placeholder" % placeholder)
    if l10n.MARKER not in engine:
        raise ValueError("engine is missing the l10n marker")

    keep = list(term["keep_english"]) + [
        k for k in term["keep_english_keys"] if k not in term["keep_english"]
    ]
    expect = len(parts)
    shards = []
    for index, part in enumerate(parts):
        body = json.dumps(part, ensure_ascii=False)
        head = (
            'window.__COPILOT_L10N_EXPECT__=%d;'
            '(window.__COPILOT_L10N_DICTS__=window.__COPILOT_L10N_DICTS__||[]).push(%s);\n'
            % (expect, body)
        )
        if index == 0:
            script = head + engine.replace("__KEEP_JSON__",
                                           json.dumps(keep, ensure_ascii=False))
            script = script.replace("__EXPECT__", str(expect))
            shards.append(script)
        else:
            shards.append('/*__COPILOT_L10N__*/' + head)
    return shards


def build_payload() -> bytes:
    """All shards concatenated: valid JS, with the engine last so every shard is queued."""
    shards = build_shard_scripts(max_bytes=10 ** 9)
    return ("\n".join(shards)).encode("utf-8")


def index_html_transform(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    if 'lang="zh-CN"' in text:
        return raw
    if 'lang="en"' not in text:
        raise ValueError('index.html has no lang="en" attribute')
    return text.replace('lang="en"', 'lang="zh-CN"', 1).encode("utf-8")


def make_append_transform(payload: bytes, force: bool):
    marker = l10n.MARKER.encode()

    def append(raw: bytes) -> bytes:
        if marker in raw:
            if not force:
                return raw  # already applied: make the install idempotent
            raise ValueError("asset already contains a l10n payload (use --force)")
        return raw + b"\n" + payload + b"\n"

    return append


def _plan_key(exe: str) -> str:
    import hashlib

    # Key on the *pristine* size so the cache survives the install that changes the exe.
    source = baseline_source(exe)
    size = os.path.getsize(source)
    payload = build_payload()
    return hashlib.sha1(
        ("%s|%d|%s" % (exe, size, hashlib.sha1(payload).hexdigest())).encode()
    ).hexdigest()


def plan_shards(exe: str, shards):
    """Assign each shard to a chunk, reusing a previous plan when nothing changed."""
    state = _load_state()
    cache = state.setdefault("plans", {})
    key = _plan_key(exe)
    cached = cache.get(key)
    if cached:
        paths = {a for a, _ in cached}
        found, _entry = discover_assets(exe)
        available = {p for p, _ in found}
        if paths and paths <= available:
            l10n.log("shard plan: reusing cached plan for %d shard(s)" % len(cached))
            return [(asset, shard) for (asset, _), shard in zip(cached, shards)]

    assignments = _plan_shards_uncached(exe, shards)
    cache[key] = [[a, len(s)] for a, s in assignments]
    # Keep the cache small; only the newest few layouts matter.
    if len(cache) > 8:
        for stale in list(cache)[:-8]:
            cache.pop(stale, None)
    _save_state(state)
    return assignments


def _plan_shards_uncached(exe: str, shards):
    """Assign each shard to the chunk with the most remaining room.

    Sizes are estimated from each chunk's own compression ratio instead of
    re-compressing the chunk once per shard: the real write recompresses the final
    bytes anyway, so measuring here twice was pure overhead.
    """
    found, _entry = discover_assets(exe)
    if not found:
        raise ValueError("none of the candidate chunks exist in %s" % exe)

    # Fill chunks from the largest downwards and only measure a chunk when it is about
    # to be used, so unused candidates cost nothing. Quality 10 matches what the write
    # uses (quality 9 compresses noticeably worse and would reject valid layouts).
    by_size = [c for c, info in sorted(found, key=lambda kv: -kv[1]["br_len"])]
    remaining = list(shards)
    assignments = []
    for candidate in by_size:
        if not remaining:
            break
        info = dict(found)[candidate]
        raw = info["raw"]
        baseline = len(l10n.compress_at(raw, 10))
        room = info["br_len"] - baseline
        ratio = (baseline / len(raw)) if raw else 0.25
        l10n.log("%s: headroom %d bytes, ratio %.2f"
                 % (candidate, room, ratio))
        while remaining:
            payload = len(remaining[0].encode())
            cost = int(payload * ratio * 1.35) + 512
            if room - cost < MIN_SLACK:
                break
            assignments.append((candidate, remaining.pop(0)))
            room -= cost
    if remaining:
        raise ValueError(
            "the translation payload no longer fits in the startup chunks "
            "(%d shard(s) left, %d bytes). Shorten the dictionary or add a candidate "
            "chunk." % (len(remaining), len(remaining[0].encode()))
        )

    used = sorted({a for a, _ in assignments})
    l10n.log("shard plan: %s" % ", ".join(
        "%s x%d" % (a, sum(1 for x, _ in assignments if x == a)) for a in used))
    return assignments


def apply_patch(exe: str, asset: str, dry_run: bool = False, force: bool = False):
    """Patch the startup chunk(s), the entry bootstrap and index.html in one write."""
    payload = build_payload()
    shards = build_shard_scripts()
    l10n.log("payload: %s bytes in %d shard(s)" % (len(payload), len(shards)))

    if asset in ("auto", "", None):
        assignments = plan_shards(exe, shards)
    else:
        assignments = [(asset, shard) for shard in shards]

    by_asset = {}
    for target, script in assignments:
        by_asset.setdefault(target, []).append(script)
    for target, scripts in by_asset.items():
        l10n.log("%s <- %d shard(s)" % (target, len(scripts)))

    edits = []
    for target, scripts in by_asset.items():
        combined = "\n".join(scripts).encode("utf-8")
        edits.append((target, make_append_transform(combined, force)))
    edits.append(("index.html", index_html_transform))

    used = [a for a in by_asset]
    candidates, entry_asset = discover_assets(exe)
    baseline_assets = [p for p, _ in candidates if p not in used]
    bootstrap_specs = [a for a in used if a != entry_asset]
    if bootstrap_specs:
        if not entry_asset:
            raise ValueError("could not identify the entry chunk (index-*.js)")
        edits.append((entry_asset, bootstrap_transform(bootstrap_specs)))
        baseline_assets = [a for a in baseline_assets if a != entry_asset]

    infos = l10n.rewrite_assets(exe, edits, dry_run, baseline_assets=baseline_assets)
    if not dry_run:
        _remember(exe, used[0])
    return payload, infos


def apply_patch_with_fallback(exe: str, asset: str, dry_run: bool = False):
    """apply_patch, but drop a stale remembered chunk and re-measure if it no longer fits."""
    try:
        return apply_patch(exe, asset, dry_run)
    except ValueError as exc:
        if "does not fit" not in str(exc) or asset not in ("auto", "", None):
            raise
        l10n.log("remembered chunk no longer fits; re-measuring all candidates")
        state = _load_state()
        state.pop(exe, None)
        _save_state(state)
        return apply_patch(exe, asset, dry_run)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inject the zh-CN localizer.")
    parser.add_argument("--exe", default=os.environ.get("COPILOT_EXE", l10n.DEFAULT_EXE))
    parser.add_argument("--copy", dest="to_copy",
                        help="patch this copy instead of the original executable")
    parser.add_argument("--asset", default=DEFAULT_ASSET,
                        help="startup chunk to append the payload to")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="append even if the payload is already present")
    args = parser.parse_args(argv)

    exe = args.exe
    if args.to_copy:
        if not os.path.exists(args.to_copy):
            os.makedirs(os.path.dirname(os.path.abspath(args.to_copy)), exist_ok=True)
            import shutil
            shutil.copy2(exe, args.to_copy)
            print("working copy created: %s" % args.to_copy)
        exe = args.to_copy

    os.makedirs(BUILD, exist_ok=True)
    payload_path = os.path.join(BUILD, "zh-cn.payload.js")

    if not args.dry_run and is_current(exe, args.asset):
        print("already up to date: this payload is installed")
        return 0

    payload, infos = apply_patch_with_fallback(exe, args.asset, args.dry_run)
    with open(payload_path, "wb") as fh:
        fh.write(payload)
    print("payload: %d bytes -> %s" % (len(payload), payload_path))
    for info in infos:
        print(json.dumps(info, ensure_ascii=False, indent=2))

    if not args.dry_run:
        print("\nDone. Restart the app to see the localized UI.")
        print("Undo with: python copilot_l10n.py restore --exe \"%s\"" % exe)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, LookupError, FileNotFoundError, PermissionError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        if isinstance(exc, PermissionError):
            print("hint: close the GitHub Copilot app first, or pass --copy <file>.",
                  file=sys.stderr)
        raise SystemExit(1)
