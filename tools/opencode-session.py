#!/usr/bin/env python3
"""Dump / list OpenCode sessions from ~/.local/share/opencode/opencode.db.

Usage:
  python opencode-session.py list [--query TEXT] [--limit N] [--days N]
  python opencode-session.py dump <ses_id|title-words> [--out FILE] [--tail N] [--full]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
CONTINUE_PING = "Continue if you have next steps"


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise SystemExit(f"opencode.db not found: {DB}")
    uri = f"file:{DB}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        con.execute("SELECT 1 FROM session LIMIT 1").fetchone()
        return con
    except sqlite3.OperationalError:
        tmpdir = Path(tempfile.mkdtemp(prefix="opencode-db-"))
        dst = tmpdir / "opencode.db"
        shutil.copy2(DB, dst)
        for suf in ("-wal", "-shm"):
            src = Path(str(DB) + suf)
            if src.exists():
                shutil.copy2(src, Path(str(dst) + suf))
        con = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con


def ts(ms) -> str:
    if not ms:
        return "-"
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")


def parse_json(raw):
    if isinstance(raw, (dict, list)):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def cmd_list(con: sqlite3.Connection, query: str | None, limit: int, days: int | None) -> int:
    sql = """
        SELECT s.id, s.slug, s.title, s.directory, s.agent, s.cost,
               s.time_created, s.time_updated,
               (SELECT COUNT(*) FROM message m WHERE m.session_id = s.id) AS msgs
        FROM session s
    """
    where = []
    args: list = []
    if query:
        like = f"%{query}%"
        where.append("(s.id LIKE ? OR s.slug LIKE ? OR s.title LIKE ? OR s.directory LIKE ?)")
        args.extend([like, like, like, like])
    if days:
        cutoff = int((dt.datetime.now() - dt.timedelta(days=days)).timestamp() * 1000)
        where.append("s.time_updated >= ?")
        args.append(cutoff)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.time_updated DESC LIMIT ?"
    args.append(limit)
    rows = con.execute(sql, args).fetchall()
    if not rows:
        print("no sessions")
        return 1
    fmt = "{:<28}  {:16}  {:>5}  {:>7}  {}"
    print(fmt.format("id", "updated", "msgs", "cost", "title"))
    for r in rows:
        title = (r["title"] or "")[:70]
        print(fmt.format(r["id"], ts(r["time_updated"]), r["msgs"] or 0, f"${r['cost'] or 0:.3f}", title))
    return 0


def resolve(con: sqlite3.Connection, ref: str) -> sqlite3.Row | None:
    ref = ref.strip()
    row = con.execute("SELECT * FROM session WHERE id = ?", (ref,)).fetchone()
    if row:
        return row
    like = f"%{ref}%"
    rows = con.execute(
        """SELECT * FROM session
           WHERE id LIKE ? OR slug LIKE ? OR title LIKE ?
           ORDER BY time_updated DESC LIMIT 8""",
        (like, like, like),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    if not rows:
        return None
    print(f"ambiguous match for {ref!r}:", file=sys.stderr)
    for r in rows:
        print(f"  {r['id']}  {r['title']}", file=sys.stderr)
    return None


def tool_path(inp: dict) -> str | None:
    if not isinstance(inp, dict):
        return None
    for k in ("filePath", "file_path", "path"):
        v = inp.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def excerpt(text: str, limit: int, full: bool) -> str:
    if full or len(text) <= limit:
        return text
    head, tail = limit // 2, limit // 4
    return (
        text[:head]
        + f"\n\n...[{len(text) - head - tail} chars omitted; pass --full]...\n\n"
        + text[-tail:]
    )


def dump_session(con: sqlite3.Connection, ses: sqlite3.Row, tail: int, full: bool) -> str:
    sid = ses["id"]
    msgs = con.execute(
        "SELECT id, time_created, data FROM message WHERE session_id = ? ORDER BY time_created",
        (sid,),
    ).fetchall()
    parts = con.execute(
        "SELECT message_id, time_created, data FROM part WHERE session_id = ? ORDER BY time_created",
        (sid,),
    ).fetchall()
    todos = con.execute(
        "SELECT content, status, priority, position FROM todo WHERE session_id = ? ORDER BY position",
        (sid,),
    ).fetchall()

    parts_by_msg: dict[str, list] = defaultdict(list)
    for p in parts:
        parts_by_msg[p["message_id"]].append(parse_json(p["data"]))

    user_texts: list[tuple[str, str]] = []
    assistant_texts: list[str] = []
    tool_hist: Counter = Counter()
    file_ops: list[tuple[str, str]] = []
    seen_ops: set[tuple[str, str]] = set()
    pings = 0

    for m in msgs:
        meta = parse_json(m["data"])
        role = meta.get("role")
        for d in parts_by_msg.get(m["id"], []):
            t = d.get("type")
            if t == "tool":
                tool = d.get("tool") or "?"
                tool_hist[tool] += 1
                state = d.get("state") or {}
                inp = state.get("input") if isinstance(state, dict) else None
                if not isinstance(inp, dict):
                    inp = d.get("input") or {}
                path = tool_path(inp) if isinstance(inp, dict) else None
                if tool in ("write", "edit", "apply_patch", "strreplace", "str_replace", "multiedit") and path:
                    key = (tool, path)
                    if key not in seen_ops:
                        seen_ops.add(key)
                        file_ops.append(key)
            if t == "text" and d.get("text"):
                txt = d["text"]
                if role == "user":
                    if txt.startswith(CONTINUE_PING):
                        pings += 1
                        continue
                    user_texts.append((ts(m["time_created"]), txt))
                elif role == "assistant":
                    assistant_texts.append(txt)

    model = parse_json(ses["model"])
    model_id = model.get("id") if isinstance(model, dict) else ses["model"]

    lines: list[str] = []
    a = lines.append
    a(f"# OpenCode session {sid}")
    a("")
    a(f"- title: {ses['title']}")
    a(f"- slug: {ses['slug']}")
    a(f"- directory: {ses['directory']}")
    a(f"- agent: {ses['agent']}  model: {model_id}")
    a(f"- created: {ts(ses['time_created'])}  updated: {ts(ses['time_updated'])}")
    a(f"- cost: ${ses['cost'] or 0:.4f}")
    a(f"- messages: {len(msgs)}  parts: {len(parts)}")
    a(f"- user turns (excl. continue-pings): {len(user_texts)}  pings skipped: {pings}")
    a("")

    a("## Todos")
    if not todos:
        a("(none)")
    else:
        for t in todos:
            a(f"- [{t['status']}] ({t['priority']}) {t['content']}")
    a("")

    a("## Tool histogram")
    if not tool_hist:
        a("(none)")
    else:
        for k, v in tool_hist.most_common():
            a(f"- {k}: {v}")
    a("")

    a("## File write/edit (unique, order of first occurrence)")
    if not file_ops:
        a("(none)")
    else:
        for tool, path in file_ops:
            a(f"- {tool}: {path}")
    a("")

    a("## User messages")
    if not user_texts:
        a("(none)")
    for i, (when, txt) in enumerate(user_texts, 1):
        a(f"\n### USER {i} @ {when} ({len(txt)} chars)\n")
        a(excerpt(txt, 6000 if i == 1 else 4000, full))
        a("")

    a("## Last assistant texts")
    tail_blocks = assistant_texts[-tail:] if tail else assistant_texts
    if not tail_blocks:
        a("(none)")
    for i, txt in enumerate(tail_blocks, 1):
        a(f"\n### ASSISTANT-TAIL {i} ({len(txt)} chars)\n")
        a(excerpt(txt, 2500, full))
        a("")

    a("## Next-agent handoff (fill after reading dump + disk)")
    a("- leftover: ")
    a("- next step: ")
    a("- do not trust todos blindly (often stale vs last user turn)")
    a("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="List or dump OpenCode sessions")
    sub = p.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list", help="recent sessions")
    lp.add_argument("--query", "-q", default=None)
    lp.add_argument("--limit", type=int, default=30)
    lp.add_argument("--days", type=int, default=None)

    dp = sub.add_parser("dump", help="dump one session to markdown")
    dp.add_argument("ref", help="ses_… id, slug, or title substring")
    dp.add_argument("--out", "-o", default=None)
    dp.add_argument("--tail", type=int, default=8, help="last N assistant texts")
    dp.add_argument("--full", action="store_true", help="do not truncate long texts")

    args = p.parse_args(argv)
    con = connect()
    try:
        if args.cmd == "list":
            return cmd_list(con, args.query, args.limit, args.days)
        ses = resolve(con, args.ref)
        if ses is None:
            print(f"session not found: {args.ref}", file=sys.stderr)
            cmd_list(con, args.ref, 15, None)
            return 1
        text = dump_session(con, ses, args.tail, args.full)
        if args.out:
            out = Path(args.out)
            out.write_text(text, encoding="utf-8")
            print(f"wrote {out} ({out.stat().st_size} bytes)  id={ses['id']}")
        else:
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
