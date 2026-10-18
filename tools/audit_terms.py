"""audit_terms.py - terminology and punctuation consistency checks.

Checks, in order of usefulness:

  1. banned synonyms      - a term rendered with a competing Chinese word
  2. label punctuation    - a short label ending with 。 although the source has none
  3. ellipsis / colon     - "..." vs "…" and ':' vs '：' used inconsistently
  4. duplicate renderings - one short Chinese value reused for unrelated English keys

    python tools/audit_terms.py
    python tools/audit_terms.py --emit-overrides   # write i18n/zz-consistency.extra.json
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

# term -> (canonical rendering, renderings that must not appear next to that term)
SYNONYMS = {
    "session": ("会话", ["对话"]),
    "issue": ("Issue", ["议题", "问题"]),
    "repository": ("仓库", ["存储库", "版本库"]),
    "review": ("审核", ["审查", "评审"]),
    "agent": ("Agent", ["代理", "智能体"]),
    "workspace": ("工作区", ["工作空间"]),
    "usage": ("用量", ["使用量"]),
    "setting": ("设置", ["设定", "首选项"]),
    "prompt": ("提示词", ["提示语"]),
    "assignee": ("负责人", ["经办人", "受理人"]),
    "notification": ("通知", ["提醒消息"]),
    "terminal": ("终端", ["命令行"]),
    "label": ("标签", ["标记"]),
    "milestone": ("里程碑", ["阶段目标"]),
    "attachment": ("附件", ["附加文件"]),
    "extension": ("扩展", ["插件"]),
    "plugin": ("插件", ["扩展"]),
    "commit": ("提交", ["commit"]),
    "branch": ("分支", ["branch"]),
    "skill": ("Skill", ["技能", "技巧"]),
    "merge": ("合并", ["归并"]),
}

LABEL_END = re.compile(r"[。！？]$")


def term_present(english: str, term: str) -> bool:
    return re.search(r"\b%s\b" % re.escape(term), english, re.I) is not None


def fix_value(english: str, zh: str) -> str:
    out = zh
    for term, (canon, banned) in SYNONYMS.items():
        if not term_present(english, term):
            continue
        for word in banned:
            if word in out and canon not in out:
                out = out.replace(word, canon)
    if LABEL_END.search(out) and not english.rstrip().endswith((".", "!", "?")):
        out = out.rstrip("。！？")
    out = out.replace("...", "…")
    out = re.sub(r"([\u4e00-\u9fff]):\s*", r"\1：", out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-overrides", action="store_true")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    dictionary = apply_zh.load_dictionary()
    print("entries: %d\n" % len(dictionary))

    findings = []

    print("== banned synonyms ==")
    shown = 0
    for en, zh in sorted(dictionary.items()):
        for term, (canon, banned) in SYNONYMS.items():
            if not term_present(en, term):
                continue
            for word in banned:
                if word in zh:
                    findings.append((en, zh))
                    if shown < args.limit:
                        print("  %-44s %-30s  %s -> %s" % (en, zh, term, word))
                        shown += 1
    print("  total: %d\n" % (len(findings)))

    punct = []
    print("== label ends with a full stop / ellipsis / colon ==")
    for en, zh in sorted(dictionary.items()):
        why = None
        if LABEL_END.search(zh) and not en.rstrip().endswith((".", "!", "?")):
            why = "label should not end with %s" % zh[-1]
        elif "..." in zh:
            why = "use '…' instead of '...'"
        elif re.search(r"[\u4e00-\u9fff]:", zh):
            why = "use '：' after Chinese"
        if why:
            punct.append((en, zh))
            if len(punct) <= args.limit:
                print("  %-44s %-30s %s" % (en, zh, why))
    print("  total: %d\n" % len(punct))
    findings.extend(punct)

    zh_map = collections.defaultdict(set)
    for en, zh in dictionary.items():
        if len(zh) <= 6 and len(en.split()) == 1:
            zh_map[zh].add(en.lower())
    ambiguous = {k: v for k, v in zh_map.items() if len(v) > 1}
    print("== short renderings shared by several English words: %d ==" % len(ambiguous))
    for zh, english in sorted(ambiguous.items(), key=lambda kv: -len(kv[1]))[:20]:
        print("  %-10s <- %s" % (zh, ", ".join(sorted(english))))
    print("\ntotal findings: %d" % len(findings))

    if args.emit_overrides:
        fixes = {}
        for en, zh in findings:
            fixed = fix_value(en, zh)
            if fixed != zh:
                fixes[en] = fixed
        path = os.path.join(ROOT, "i18n", "zz-consistency.extra.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(fixes, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print("wrote %d overrides to %s" % (len(fixes), path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
