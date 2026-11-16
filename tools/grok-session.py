#!/usr/bin/env python3
"""List / dump Grok Build sessions from ~/.grok/sessions.

Usage:
  python grok-session.py list [--query TEXT] [--limit N] [--days N]
  python grok-session.py dump [id|title-words|latest] [--out FILE] [--tail N] [--full]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / ".grok" / "sessions"
USER_Q = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def ts(d: dt.datetime | None) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if d else "-"


def load_summary(sid_dir: Path) -> dict | None:
    p = sid_dir / "summary.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    info = data.get("info") or {}
    return {
        "id": info.get("id") or sid_dir.name,
        "cwd": info.get("cwd") or data.get("cwd") or "",
        "title": data.get("generated_title") or data.get("session_summary") or "",
        "last": data.get("last_turn_summary") or "",
        "updated": parse_iso(data.get("updated_at") or data.get("last_active_at")),
        "created": parse_iso(data.get("created_at")),
        "model": data.get("current_model_id") or "",
        "msgs": data.get("num_chat_messages") or data.get("num_messages") or 0,
        "dir": sid_dir,
    }


def iter_sessions() -> list[dict]:
    out = []
    if not ROOT.exists():
        return out
    for cwd_dir in ROOT.iterdir():
        if not cwd_dir.is_dir():
            continue
        for sid_dir in cwd_dir.iterdir():
            if not sid_dir.is_dir():
                continue
            if not (sid_dir / "summary.json").exists():
                continue
            rec = load_summary(sid_dir)
            if rec:
                out.append(rec)
    out.sort(key=lambda r: r["updated"] or dt.datetime.min, reverse=True)
    return out


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                parts.append(x.get("text") or "")
            elif isinstance(x, str):
                parts.append(x)
        return "\n".join(parts)
    return ""


def user_queries(sid_dir: Path) -> list[str]:
    p = sid_dir / "chat_history.jsonl"
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "user":
                continue
            text = extract_text(obj.get("content"))
            m = USER_Q.search(text)
            if m:
                q = m.group(1).strip()
                if q:
                    out.append(q)
    return out


def assistant_texts(sid_dir: Path) -> list[str]:
    p = sid_dir / "chat_history.jsonl"
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            text = extract_text(obj.get("content")).strip()
            if text:
                out.append(text)
    return out


def excerpt(text: str, limit: int, full: bool) -> str:
    if full or len(text) <= limit:
        return text
    head, tail = limit // 2, limit // 4
    return (
        text[:head]
        + f"\n\n...[{len(text) - head - tail} chars omitted; pass --full]...\n\n"
        + text[-tail:]
    )


def resolve(sessions: list[dict], ref: str | None) -> dict | None:
    if not sessions:
        return None
    if not ref or ref.lower() in ("latest", "last", "последняя", "последний"):
        return sessions[0]
    ref = ref.strip()
    exact = [s for s in sessions if s["id"] == ref]
    if exact:
        return exact[0]
    q = ref.lower()
    hits = [
        s
        for s in sessions
        if q in s["id"].lower() or q in (s["title"] or "").lower() or q in (s["last"] or "").lower()
    ]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print(f"ambiguous match for {ref!r}:", file=sys.stderr)
        for s in hits[:8]:
            print(f"  {s['id']}  {s['title']}", file=sys.stderr)
        return None
    return None


def cmd_list(query: str | None, limit: int, days: int | None) -> int:
    rows = iter_sessions()
    if query:
        q = query.lower()
        rows = [
            r
            for r in rows
            if q in r["id"].lower()
            or q in (r["title"] or "").lower()
            or q in (r["cwd"] or "").lower()
            or q in (r["last"] or "").lower()
        ]
    if days:
        cutoff = dt.datetime.now() - dt.timedelta(days=days)
        rows = [r for r in rows if r["updated"] and r["updated"] >= cutoff]
    rows = rows[:limit]
    if not rows:
        print("no grok sessions")
        return 1
    fmt = "{:<36}  {:16}  {:>4}  {}"
    print(fmt.format("id", "updated", "msgs", "title"))
    for r in rows:
        title = (r["title"] or r["last"] or "")[:70]
        print(fmt.format(r["id"], ts(r["updated"]), r["msgs"], title))
    return 0


def dump_session(ses: dict, tail: int, full: bool) -> str:
    users = user_queries(ses["dir"])
    asst = assistant_texts(ses["dir"])
    lines: list[str] = []
    a = lines.append
    a(f"# Grok session {ses['id']}")
    a("")
    a(f"- title: {ses['title']}")
    a(f"- cwd: {ses['cwd']}")
    a(f"- dir: {ses['dir']}")
    a(f"- model: {ses['model']}")
    a(f"- created: {ts(ses['created'])}  updated: {ts(ses['updated'])}")
    a(f"- chat messages (summary): {ses['msgs']}")
    a(f"- last_turn_summary: {ses['last']}")
    a("")
    a("## User queries")
    if not users:
        a("(none)")
    for i, t in enumerate(users, 1):
        a(f"\n### USER {i} ({len(t)} chars)\n")
        a(excerpt(t, 4000, full))
        a("")
    a("## Last assistant texts")
    blocks = asst[-tail:] if tail else asst
    if not blocks:
        a("(none)")
    for i, t in enumerate(blocks, 1):
        a(f"\n### ASSISTANT-TAIL {i} ({len(t)} chars)\n")
        a(excerpt(t, 2500, full))
        a("")
    a("## Next-agent handoff (fill after reading dump + disk)")
    a("- leftover: ")
    a("- next step: ")
    a("- do not trust last_turn_summary blindly — verify files on disk")
    a("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="List or dump Grok Build sessions")
    sub = p.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list")
    lp.add_argument("--query", "-q", default=None)
    lp.add_argument("--limit", type=int, default=20)
    lp.add_argument("--days", type=int, default=None)

    dp = sub.add_parser("dump")
    dp.add_argument("ref", nargs="?", default="latest")
    dp.add_argument("--out", "-o", default=None)
    dp.add_argument("--tail", type=int, default=8)
    dp.add_argument("--full", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args.query, args.limit, args.days)
    sessions = iter_sessions()
    ses = resolve(sessions, args.ref)
    if ses is None:
        print(f"session not found: {args.ref}", file=sys.stderr)
        cmd_list(args.ref if args.ref not in ("latest",) else None, 15, None)
        return 1
    text = dump_session(ses, args.tail, args.full)
    if args.out:
        out = Path(args.out)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out} ({out.stat().st_size} bytes)  id={ses['id']}")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
