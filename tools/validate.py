#!/usr/bin/env python3
"""Check submissions before they are merged.

  python tools/validate.py                      # every submission
  python tools/validate.py submissions/<name>   # one

Checks that the files are there, that run.json records when, what and where
(date and time, models, OS, commits), that every scored model was run, that
logs open, and that nothing that looks like a credential slipped in.
"""
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET = re.compile(r"Bearer\s+\S{8,}|\bsk-[A-Za-z0-9_-]{16,}|\"?(api[_-]?key|authorization)\"?\s*[:=]\s*\"[^\"]{8,}", re.I)
TRAITS = ["curiosity", "creativity", "patience", "accommodation", "hubris", "sycophancy", "instruction_following"]


def check(d):
    errs = []
    run_f, scores_f = d / "run.json", d / "scores.json"
    if not run_f.is_file() or not scores_f.is_file():
        return ["missing run.json or scores.json"]
    run, scores = json.loads(run_f.read_text()), json.loads(scores_f.read_text())
    for path in ["started", "finished", "settings.models", "machine.os", "machine.python", "code.disposition", "code.enclosure"]:
        cur = run
        for k in path.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
        if not cur:
            errs.append(f"run.json: missing {path}")
    if not scores.get("judge"):
        errs.append("scores.json: missing judge")
    ran = set((run.get("settings") or {}).get("models") or [])
    for model, m in (scores.get("models") or {}).items():
        if model not in ran:
            errs.append(f"scores.json: {model} was not in the batch")
        missing = [t for t in TRAITS if t not in (m.get("traits") or {})]
        if missing:
            errs.append(f"scores.json: {model} lacks {', '.join(missing)}")
    for e in run.get("episodes") or []:
        if e.get("log") and not (d / (e["log"] + ".gz")).is_file():
            errs.append(f"log missing: {e['log']}.gz")
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = gzip.open(f, "rt", errors="replace").read() if f.suffix == ".gz" else f.read_text(errors="replace")
        except OSError as ex:
            errs.append(f"{f.relative_to(d)}: unreadable ({ex})")
            continue
        if SECRET.search(text):
            errs.append(f"{f.relative_to(d)}: looks like it contains a credential")
    return errs


def main():
    dirs = [Path(a) for a in sys.argv[1:]] or sorted(p for p in (ROOT / "submissions").iterdir() if p.is_dir())
    bad = 0
    for d in dirs:
        errs = check(d)
        print(f"{'FAIL' if errs else 'ok  '}  {d.name}")
        for e in errs:
            print(f"      {e}")
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
