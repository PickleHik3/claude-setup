#!/usr/bin/env python3
"""SessionEnd / SubagentStop hook: run `cc-usage collect --quiet`, never block or fail the session.

It always exits 0. Output and errors go to hook.log beside the usage database, not to the session.
Relies on bin/cc-usage's module (usage/cc_usage.py) being next to this file's real path in the
repo; checked on Claude Code 2.1.330 (2026-11-22), whose hooks pass JSON on stdin that is ignored here.
"""
import contextlib, os, sys, traceback

try:
    sys.stdin.read()
except Exception:
    pass
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "usage"))
    import cc_usage
    log_dir = os.path.dirname(cc_usage.db_path()) or "."
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "hook.log"), "a") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            cc_usage.main(["collect", "--quiet"])
        except BaseException:
            traceback.print_exc()
except BaseException:
    pass
sys.exit(0)
