"""uia_common.py - shared, safe helpers for reading the GitHub Copilot window.

Safety rules baked in here:
  * the target window is identified by process executable (github.exe) and window
    class (Tauri Window), never by title alone -- an Edge tab can also be titled
    "GitHub Copilot"
  * nothing ever performs a physical mouse click: activation goes through the
    accessibility Invoke/Select patterns, which do not move the cursor and cannot
    land on whatever window happens to be on top
  * no text is typed and no form is submitted
"""

from __future__ import annotations

import collections
import ctypes
import ctypes.wintypes as wt
import os
import re
import sys
import time

import uiautomation as auto

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TARGET_EXE = "github.exe"
TARGET_CLASS = "Tauri Window"

HAS_LATIN = re.compile(r"[A-Za-z]{2}")
HAS_CJK = re.compile(r"[\u4e00-\u9fff]")

# Text that is not UI copy: paths, shortcuts, identifiers, transcript chrome.
NOISE = [
    re.compile(r"^[A-Za-z]:[\\/]"),
    re.compile(r"^\.{0,2}/"),
    re.compile(r"^(Ctrl|Control|Alt|Shift|Cmd|Meta|Option)\b", re.I),
    re.compile(r"^[\w.-]+\.(js|mjs|ts|tsx|jsx|py|md|json|exe|cmd|bat|txt|yml|yaml|css|html)$", re.I),
    re.compile(r"^[A-Z_]{3,}$"),
    re.compile(r"^[0-9a-f]{7,}$", re.I),
    re.compile(r"^[\w-]+/[\w-]+$"),
    re.compile(r"^[a-z]+[A-Z]\w+$"),
    re.compile(r"^(cd|git|npm|node|python|pip|gh|npx|yarn|pnpm)\s"),
    re.compile(r"[\\/][\w.-]+[\\/]"),
    re.compile(r"[`{}<>]|=>|::"),
    re.compile(r"^[·•]\s*[\w.-]+$"),
    re.compile(r"^[a-z][\w-]*$"),                       # bare lowercase identifiers
    re.compile(r"^(and )?\d+ other tool calls?$"),
    re.compile(r"\band \d+ other tool calls?\b"),
    re.compile(r"^Thought for [\d.]+m?s$"),
    re.compile(r"^Reasoning:\s"),
    re.compile(r",\s*show timestamp$"),
    re.compile(r"^Chrome Legacy Window$"),
    re.compile(r"^[\d\s.,%·-]+$"),
]


def process_name(pid: int) -> str:
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
    return ""


def find_app_window():
    """The Copilot window only: github.exe + 'Tauri Window' class."""
    for win in auto.GetRootControl().GetChildren():
        try:
            exe = process_name(win.ProcessId)
            if not exe:
                continue
            if os.path.basename(exe).lower() != TARGET_EXE:
                continue
            if TARGET_CLASS and (win.ClassName or "") != TARGET_CLASS:
                continue
            return win
        except Exception:
            continue
    return None


def describe_window(win) -> str:
    try:
        exe = process_name(win.ProcessId)
        return "%s | pid=%s | class=%s | exe=%s" % (
            win.Name, win.ProcessId, win.ClassName, os.path.basename(exe))
    except Exception:
        return "?"


def walk(control, out, depth=0, max_depth=60):
    try:
        out.append((depth, control.ControlTypeName or "", control.Name or ""))
    except Exception:
        return
    if depth >= max_depth:
        return
    try:
        children = control.GetChildren()
    except Exception:
        return
    for child in children:
        walk(child, out, depth + 1, max_depth)


def wake(window, timeout: float = 10.0) -> bool:
    """Chromium enables accessibility lazily; poke the tree until it fills in."""
    deadline = time.time() + timeout
    best = 0
    while time.time() < deadline:
        rows = []
        walk(window, rows, max_depth=12)
        best = max(best, len(rows))
        if len(rows) > 40:
            return True
        time.sleep(0.5)
    return best > 12


def collect(window, seconds: float = 1.5):
    seen = collections.Counter()
    deadline = time.time() + seconds
    while True:
        rows = []
        walk(window, rows)
        for _depth, _ctype, name in rows:
            if name:
                seen[name.strip()] += 1
        if time.time() >= deadline:
            break
        time.sleep(0.4)
    return seen


def is_candidate(text: str, min_len: int = 2, max_len: int = 120) -> bool:
    text = text.strip()
    if not (min_len <= len(text) <= max_len):
        return False
    if not HAS_LATIN.search(text):
        return False
    if HAS_CJK.search(text):
        return False
    for pattern in NOISE:
        if pattern.search(text):
            return False
    return True


def find_control(root, label: str, depth=0):
    """Find a navigation control by accessible name (exact or prefix match)."""
    if depth > 40:
        return None
    try:
        name = (root.Name or "").strip()
        ctype = root.ControlTypeName or ""
        if ctype in ("ButtonControl", "ListItemControl", "TreeItemControl",
                     "TabItemControl", "HyperlinkControl", "MenuItemControl"):
            if name == label or name.startswith(label):
                return root
        for child in root.GetChildren():
            hit = find_control(child, label, depth + 1)
            if hit is not None:
                return hit
    except Exception:
        return None
    return None


def activate(control) -> str:
    """Activate a control through accessibility patterns only (no physical click)."""
    try:
        control.GetInvokePattern().Invoke()
        return "invoke"
    except Exception:
        pass
    try:
        control.GetSelectionItemPattern().Select()
        return "select"
    except Exception:
        pass
    try:
        control.GetLegacyIAccessiblePattern().DoDefaultAction()
        return "legacy"
    except Exception:
        pass
    return ""


def gap_list(texts, dictionary, keep):
    gaps = []
    for text, count in texts.most_common():
        if not is_candidate(text):
            continue
        if text in dictionary or text.strip().lower() in keep:
            continue
        gaps.append((count, text))
    return gaps
