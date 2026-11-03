#!/usr/bin/env python3
"""Compact view of a uiautomator dump read from stdin.

  ui.py                 every node that has text, a description, an id, or is interactive
  ui.py --all           every node
  ui.py --find TEXT     nodes whose text/desc/id contains TEXT (case-insensitive)
  ui.py --find TEXT --xy   just "x y" of the first match's center (for `ad tap`)
  ui.py --find TEXT --bounds   "x1 y1 x2 y2" of every match, in screen order (for `ad zoom`)
"""
import re
import sys
import xml.etree.ElementTree as ET

args = sys.argv[1:]
show_all = "--all" in args
xy_only = "--xy" in args
bounds_only = "--bounds" in args
needle = None
if "--find" in args:
    needle = args[args.index("--find") + 1].lower()

tree = ET.parse(sys.stdin)
BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def walk(node, depth, out):
    for child in node:
        if child.tag == "node":
            out.append((depth, child))
            walk(child, depth + 1, out)


nodes = []
walk(tree.getroot(), 0, nodes)

rows = []
for depth, n in nodes:
    g = n.get
    text, desc, rid = g("text", ""), g("content-desc", ""), g("resource-id", "")
    flags = [f for f in ("clickable", "long-clickable", "checkable", "scrollable", "focused", "selected", "password")
             if g(f) == "true"]
    if g("checkable") == "true":
        flags.append("checked" if g("checked") == "true" else "unchecked")
    if g("enabled") == "false":
        flags.append("disabled")
    interesting = text or desc or rid or "clickable" in flags or "scrollable" in flags
    if needle is not None:
        hay = f"{text} {desc} {rid}".lower()
        if needle not in hay:
            continue
    elif not (show_all or interesting):
        continue
    m = BOUNDS.match(g("bounds", ""))
    if not m:
        continue
    x1, y1, x2, y2 = map(int, m.groups())
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    rows.append((depth, n, text, desc, rid, flags, (x1, y1, x2, y2), (cx, cy)))

if bounds_only:
    for r in rows:
        x1, y1, x2, y2 = r[6]
        if x2 > x1 and y2 > y1:
            print(x1, y1, x2, y2)
    sys.exit(0 if rows else 1)

if xy_only:
    # prefer a clickable match; else the first
    pick = next((r for r in rows if "clickable" in r[5]), rows[0] if rows else None)
    if pick:
        print(f"{pick[7][0]} {pick[7][1]}")
    sys.exit(0 if pick else 1)

pkg = nodes[0][1].get("package", "?") if nodes else "?"
print(f"# package={pkg} nodes={len(rows)}")
for depth, n, text, desc, rid, flags, b, c in rows:
    cls = n.get("class", "").rsplit(".", 1)[-1]
    parts = [cls]
    if text:
        parts.append(f'text="{text[:60]}"')
    if desc:
        parts.append(f'desc="{desc[:60]}"')
    if rid:
        parts.append(f"id={rid.split('/')[-1]}")
    if flags:
        parts.append("[" + ",".join(flags) + "]")
    parts.append(f"@{c[0]},{c[1]} ({b[0]},{b[1]})-({b[2]},{b[3]})")
    print("  " * min(depth, 6) + " ".join(parts))
