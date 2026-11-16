#!/usr/bin/env python3
"""
opencode-cost.py - OpenCode + Grok Build cost/session dashboard.

OpenCode: ~/.local/share/opencode/opencode.db (session.cost + token columns).
Grok: ~/.grok/sessions/<urlencoded-cwd>/<id>/summary.json (+ signals.json).
Grok does not store a dollar cost; do not invent one.

Usage:
  python opencode-cost.py                 # OpenCode summary + Grok session section
  python opencode-cost.py --json          # flat rows as JSON (source=opencode|grok)
  python opencode-cost.py --days 7        # last N days (OpenCode time_created, Grok updated_at)
  python opencode-cost.py --hours         # hourly histogram (OpenCode $ only)
  python opencode-cost.py --html          # write opencode-cost.html and print file:// URI
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import sys
from pathlib import Path

DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
GROK_SESSIONS = Path.home() / ".grok" / "sessions"


def load() -> list[dict]:
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    rows = cur.execute("""
        SELECT s.time_created, s.cost,
               s.tokens_input, s.tokens_output, s.tokens_reasoning,
               s.tokens_cache_read, s.tokens_cache_write,
               s.slug, s.title, s.agent, s.model,
               p.worktree
        FROM session s LEFT JOIN project p ON s.project_id = p.id
        ORDER BY s.time_created
    """).fetchall()
    out = []
    for r in rows:
        model = None
        try:
            m = json.loads(r[10]) if isinstance(r[10], str) else r[10]
            model = m.get("id") if isinstance(m, dict) else m
        except (json.JSONDecodeError, AttributeError):
            model = r[10]
        out.append({
            "source": "opencode",
            "ts": datetime.datetime.fromtimestamp((r[0] or 0) / 1000) if r[0] else None,
            "cost": r[1] or 0.0,
            "tokens": {
                "input": r[2] or 0,
                "output": r[3] or 0,
                "reasoning": r[4] or 0,
                "cache_read": r[5] or 0,
                "cache_write": r[6] or 0,
            },
            "slug": r[7] or "",
            "title": (r[8] or "")[:60],
            "agent": r[9] or "main",
            "model": model or "unknown",
            "project": r[11] or "global",
        })
    con.close()
    return out


def parse_iso_local(s: str | None) -> datetime.datetime | None:
    if not s:
        return None
    try:
        d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d


def load_signals(sid_dir: Path) -> dict:
    p = sid_dir / "signals.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "turns": data.get("turnCount") or 0,
        "context_tokens_used": data.get("contextTokensUsed") or 0,
        "context_window_tokens": data.get("contextWindowTokens") or 0,
        "duration_s": data.get("sessionDurationSeconds") or 0,
        "tool_calls": data.get("toolCallCount") or 0,
        "primary_model": data.get("primaryModelId") or "",
    }


def load_grok() -> list[dict]:
    """Index Grok sessions from summary.json. No dollar cost is stored."""
    out: list[dict] = []
    if not GROK_SESSIONS.exists():
        return out
    for cwd_dir in GROK_SESSIONS.iterdir():
        if not cwd_dir.is_dir():
            continue
        for sid_dir in cwd_dir.iterdir():
            if not sid_dir.is_dir():
                continue
            summary_path = sid_dir / "summary.json"
            if not summary_path.exists():
                continue
            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            info = data.get("info") or {}
            sig = load_signals(sid_dir)
            updated = parse_iso_local(data.get("updated_at") or data.get("last_active_at"))
            created = parse_iso_local(data.get("created_at"))
            cwd = info.get("cwd") or data.get("cwd") or ""
            out.append({
                "source": "grok",
                "id": info.get("id") or sid_dir.name,
                "ts": updated,
                "created": created,
                "cost": None,
                "title": (data.get("generated_title") or data.get("session_summary") or "")[:80],
                "cwd": cwd,
                "project": cwd,
                "model": data.get("current_model_id") or sig.get("primary_model") or "",
                "msgs": data.get("num_chat_messages") or data.get("num_messages") or 0,
                "turns": sig.get("turns") or 0,
                "last": (data.get("last_turn_summary") or "")[:80],
                "context_tokens_used": sig.get("context_tokens_used") or 0,
                "duration_s": sig.get("duration_s") or 0,
            })
    out.sort(key=lambda r: r["ts"] or datetime.datetime.min, reverse=True)
    return out


def apply_days(rows: list[dict], days: int | None) -> list[dict]:
    if not days:
        return rows
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    return [r for r in rows if r.get("ts") and r["ts"] >= cutoff]


def project_short(path: str) -> str:
    if not path or path == "/":
        return "global"
    parts = Path(path).parts
    try:
        i = parts.index("Workspace")
        rest = "/".join(parts[i + 1:])
        return rest if rest else "Workspace"
    except ValueError:
        return path.replace("C:/", "").replace("C:\\", "")


HTML_OUT = Path(__file__).with_name("opencode-cost.html")


def esc(s: object) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def bar_pct(pct: float) -> str:
    w = max(0, min(100, pct))
    return f'<span class="bar"><i style="width:{w:.1f}%"></i></span> {w:.1f}%'


def write_html(oc: list[dict], grok: list[dict], days: int | None) -> Path:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    window = f"last {days} days" if days else "all sessions"
    total = sum(r["cost"] for r in oc)
    tin = sum(r["tokens"]["input"] for r in oc) if oc else 0
    tout = sum(r["tokens"]["output"] for r in oc) if oc else 0
    tr = sum(r["tokens"]["reasoning"] for r in oc) if oc else 0
    tc = sum(r["tokens"]["cache_read"] + r["tokens"]["cache_write"] for r in oc) if oc else 0
    oc_period = ""
    if oc:
        ts = [r["ts"] for r in oc if r.get("ts")]
        if ts:
            oc_period = f"{min(ts).date()} .. {max(ts).date()}"
    week_cost = sum(r["cost"] for r in oc if r.get("ts") and r["ts"] >= datetime.datetime.now() - datetime.timedelta(days=7))
    month_cost = sum(r["cost"] for r in oc if r.get("ts") and r["ts"] >= datetime.datetime.now() - datetime.timedelta(days=30))
    go_rows = ""
    for name, lim, used in (("5-hour", 12.0, total), ("week", 30.0, week_cost), ("month", 60.0, month_cost)):
        pct = used / lim * 100 if lim else 0
        go_rows += f"<tr><td>{esc(name)}</td><td>${used:.2f} / ${lim:.0f}</td><td>{bar_pct(pct)}</td></tr>"
    proj: dict[str, dict] = {}
    for r in oc:
        p = project_short(r["project"])
        a = proj.setdefault(p, {"n": 0, "cost": 0.0})
        a["n"] += 1
        a["cost"] += r["cost"]
    proj_rows = "".join(
        f"<tr><td>{esc(p)}</td><td>{a['n']}</td><td>${a['cost']:.3f}</td></tr>"
        for p, a in sorted(proj.items(), key=lambda kv: -kv[1]["cost"])
    )
    mod: dict[str, dict] = {}
    for r in oc:
        a = mod.setdefault(str(r["model"]), {"n": 0, "cost": 0.0})
        a["n"] += 1
        a["cost"] += r["cost"]
    mod_rows = "".join(
        f"<tr><td>{esc(m)}</td><td>{a['n']}</td><td>${a['cost']:.3f}</td></tr>"
        for m, a in sorted(mod.items(), key=lambda kv: -kv[1]["cost"])
    )
    top_rows = "".join(
        f"<tr><td>${r['cost']:.3f}</td><td>{esc(r['ts'].strftime('%m-%d %H:%M') if r.get('ts') else '?')}</td>"
        f"<td>{esc(r.get('slug',''))}</td><td>{esc(project_short(r.get('project') or ''))}</td>"
        f"<td>{esc(r.get('title',''))}</td></tr>"
        for r in sorted(oc, key=lambda x: -x["cost"])[:12]
    )
    grok_cwd: dict[str, dict] = {}
    for r in grok:
        p = project_short(r.get("cwd") or r.get("project") or "")
        a = grok_cwd.setdefault(p, {"n": 0, "msgs": 0, "turns": 0})
        a["n"] += 1
        a["msgs"] += r.get("msgs") or 0
        a["turns"] += r.get("turns") or 0
    grok_cwd_rows = "".join(
        f"<tr><td>{esc(p)}</td><td>{a['n']}</td><td>{a['msgs']}</td><td>{a['turns']}</td></tr>"
        for p, a in sorted(grok_cwd.items(), key=lambda kv: -kv[1]["n"])
    )
    grok_sess_rows = "".join(
        f"<tr><td>{esc(r['ts'].strftime('%m-%d %H:%M') if r.get('ts') else '?')}</td>"
        f"<td><code>{esc(r.get('id',''))}</code></td><td>{esc(project_short(r.get('cwd') or ''))}</td>"
        f"<td>{esc(r.get('model') or '')}</td><td>{esc(r.get('title') or r.get('last') or '')}</td>"
        f"<td>unknown</td></tr>"
        for r in grok[:16]
    )
    grok_ctx = sum(r.get("context_tokens_used") or 0 for r in grok)
    grok_turns = sum(r.get("turns") or 0 for r in grok)
    grok_msgs = sum(r.get("msgs") or 0 for r in grok)
    grok_dur = sum(r.get("duration_s") or 0 for r in grok) / 3600
    html = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<title>OpenCode + Grok cost dashboard</title>
<style>
  :root {{ color-scheme: dark; --bg:#12141a; --card:#1b1e27; --bd:#2a2e3a; --fg:#e8eaef; --mut:#8b90a0; --acc:#4da3ff; --ok:#6ee7b7; }}
  body {{ margin:0; font:14px/1.45 ui-sans-serif,system-ui; background:var(--bg); color:var(--fg); }}
  main {{ max-width:1100px; margin:0 auto; padding:24px 20px 48px; }}
  h1 {{ font-size:22px; margin:0 0 6px; }}
  h2 {{ font-size:15px; color:var(--mut); text-transform:uppercase; letter-spacing:.04em; margin:28px 0 8px; }}
  .sub {{ color:var(--mut); margin:0 0 18px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
  .card {{ background:var(--card); border:1px solid var(--bd); border-radius:10px; padding:12px 14px; }}
  .card b {{ display:block; font-size:20px; color:var(--acc); }}
  .card span {{ color:var(--mut); font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--bd); border-radius:10px; overflow:hidden; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--bd); font-size:13px; }}
  th {{ color:var(--mut); font-weight:600; }}
  code {{ font:12px ui-monospace,monospace; }}
  .bar {{ display:inline-block; width:120px; height:8px; background:#2a2e3a; border-radius:99px; vertical-align:middle; overflow:hidden; }}
  .bar i {{ display:block; height:100%; background:var(--acc); }}
  .note {{ color:var(--mut); font-size:12px; margin-top:10px; }}
</style></head><body><main>
<h1>OpenCode + Grok cost dashboard</h1>
<p class="sub">generated {esc(now)} · window: {esc(window)} · Grok $ is not stored in session files</p>
<div class="cards">
  <div class="card"><span>OpenCode cost</span><b>${total:.3f}</b></div>
  <div class="card"><span>OpenCode sessions</span><b>{len(oc)}</b></div>
  <div class="card"><span>Grok sessions</span><b>{len(grok)}</b></div>
  <div class="card"><span>Grok spend</span><b>unknown</b></div>
</div>
<h2>OpenCode</h2>
<p class="sub">period {esc(oc_period)} · tokens {tin:,} in / {tout:,} out / {tr:,} reasoning / {tc:,} cache</p>
<table><thead><tr><th>Go limit</th><th>used</th><th></th></tr></thead><tbody>{go_rows}</tbody></table>
<h2>Per project</h2>
<table><thead><tr><th>project</th><th>sess</th><th>cost</th></tr></thead><tbody>{proj_rows or "<tr><td colspan=3>none</td></tr>"}</tbody></table>
<h2>Per model</h2>
<table><thead><tr><th>model</th><th>sess</th><th>cost</th></tr></thead><tbody>{mod_rows or "<tr><td colspan=3>none</td></tr>"}</tbody></table>
<h2>Top OpenCode sessions</h2>
<table><thead><tr><th>$</th><th>when</th><th>slug</th><th>project</th><th>title</th></tr></thead><tbody>{top_rows or "<tr><td colspan=5>none</td></tr>"}</tbody></table>
<h2>Grok Build</h2>
<p class="sub">cost unknown · turns={grok_turns} msgs={grok_msgs} duration={grok_dur:.1f}h · context occupancy (not billed) {grok_ctx:,}</p>
<table><thead><tr><th>cwd</th><th>sess</th><th>msgs</th><th>turns</th></tr></thead><tbody>{grok_cwd_rows or "<tr><td colspan=4>none</td></tr>"}</tbody></table>
<h2>Recent Grok sessions</h2>
<table><thead><tr><th>when</th><th>id</th><th>cwd</th><th>model</th><th>title</th><th>$</th></tr></thead><tbody>{grok_sess_rows or "<tr><td colspan=6>none</td></tr>"}</tbody></table>
<p class="note">This page is a snapshot. Refresh: <code>python opencode-cost.py --html</code> (optional <code>--days N</code>).</p>
</main></body></html>
"""
    HTML_OUT.write_text(html, encoding="utf-8")
    return HTML_OUT


def print_grok(rows: list[dict]) -> None:
    print("\n=== Grok Build sessions ===")
    print(f"grok: {len(rows)} sessions, cost unknown")
    if not rows:
        print("  (no Grok sessions in this window; filter is updated_at)")
        return
    ts_ok = [r["ts"] for r in rows if r.get("ts")]
    if ts_ok:
        print(f"period:  {min(ts_ok).date()} .. {max(ts_ok).date()}  (by updated_at)")
    models = sorted({r.get("model") or "unknown" for r in rows})
    print(f"models:  {', '.join(models)}")
    ctx = sum(r.get("context_tokens_used") or 0 for r in rows)
    turns = sum(r.get("turns") or 0 for r in rows)
    dur = sum(r.get("duration_s") or 0 for r in rows)
    msgs = sum(r.get("msgs") or 0 for r in rows)
    print(f"activity: turns={turns} msgs={msgs} duration={dur / 3600:.1f}h")
    print(f"context occupancy (current window, not billed): {ctx:,} tokens")
    print()
    print("--- grok per cwd ---")
    cwd_agg: dict[str, dict] = {}
    for r in rows:
        p = project_short(r.get("cwd") or r.get("project") or "")
        a = cwd_agg.setdefault(p, {"n": 0, "msgs": 0, "turns": 0})
        a["n"] += 1
        a["msgs"] += r.get("msgs") or 0
        a["turns"] += r.get("turns") or 0
    for p, a in sorted(cwd_agg.items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {p:<34} sess={a['n']:>3} msgs={a['msgs']:>6} turns={a['turns']:>4}")
    print("\n--- recent grok sessions ---")
    for r in rows[:8]:
        d = r["ts"].strftime("%m-%d %H:%M") if r.get("ts") else "?"
        title = r.get("title") or r.get("last") or ""
        print(
            f"  {d}  {str(r.get('id', '')):<36}  "
            f"{project_short(r.get('cwd') or ''):<24}  {title[:40]}"
        )


def main() -> int:
    days = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    oc = apply_days(load(), days)
    grok = apply_days(load_grok(), days)

    if "--json" in sys.argv:
        print(json.dumps(oc + grok, ensure_ascii=False, indent=1, default=str))
        return 0

    if "--html" in sys.argv:
        path = write_html(oc, grok, days)
        print(path.resolve().as_uri())
        return 0

    if not oc and not grok:
        print("no sessions found in", DB, "or", GROK_SESSIONS)
        return 1

    if not oc:
        print("=== OpenCode cost dashboard ===")
        print("sessions: 0 | no OpenCode sessions in this window")
        print_grok(grok)
        return 0

    rows = oc
    total_cost = sum(r["cost"] for r in rows)
    tin = sum(r["tokens"]["input"] for r in rows)
    tout = sum(r["tokens"]["output"] for r in rows)
    tr = sum(r["tokens"]["reasoning"] for r in rows)
    tc = sum(r["tokens"]["cache_read"] + r["tokens"]["cache_write"] for r in rows)

    print("=== OpenCode cost dashboard ===")
    print(f"sessions: {len(rows)} | period: {min(r['ts'] for r in rows if r['ts']).date()} .. {max(r['ts'] for r in rows if r['ts']).date()}")
    print(f"cost:     ${total_cost:.3f}")
    print(f"tokens:   {tin:,} in / {tout:,} out / {tr:,} reasoning / {tc:,} cache")
    print()

    # OpenCode Go subscription limits (from docs/opencode.ai/docs/go)
    print("--- OpenCode Go limits (this period) ---")
    week_cost = sum(r["cost"] for r in rows if r["ts"] and r["ts"] >= datetime.datetime.now() - datetime.timedelta(days=7))
    month_cost = sum(r["cost"] for r in rows if r["ts"] and r["ts"] >= datetime.datetime.now() - datetime.timedelta(days=30))
    go_limits = [
        ("5-hour", 12.0, total_cost),
        ("week", 30.0, week_cost),
        ("month", 60.0, month_cost),
    ]
    for name, lim, used in go_limits:
        pct = used / lim * 100 if lim else 0
        bar = "#" * int(pct / 5)
        print(f"  {name:<7} ${used:>6.2f} / ${lim:>5.0f}  ({pct:>5.1f}%) {bar}")
    print()

    # per project
    print("--- per project ---")
    proj = {}
    for r in rows:
        p = project_short(r["project"])
        a = proj.setdefault(p, {"n": 0, "cost": 0.0, "tin": 0, "tout": 0})
        a["n"] += 1; a["cost"] += r["cost"]; a["tin"] += r["tokens"]["input"]; a["tout"] += r["tokens"]["output"]
    for p, a in sorted(proj.items(), key=lambda kv: -kv[1]["cost"]):
        print(f"  {p:<34} sess={a['n']:>3} cost=${a['cost']:>8.3f} tin={a['tin']:>9,} tout={a['tout']:>8,}")

    # per model
    print("\n--- per model ---")
    mod = {}
    for r in rows:
        a = mod.setdefault(r["model"], {"n": 0, "cost": 0.0})
        a["n"] += 1; a["cost"] += r["cost"]
    for m, a in sorted(mod.items(), key=lambda kv: -kv[1]["cost"]):
        print(f"  {str(m)[:44]:<46} sess={a['n']:>3} cost=${a['cost']:>8.3f}")

    if "--hours" in sys.argv:
        print("\n--- hourly histogram (active hours, $) ---")
        hist = {}
        for r in rows:
            if r["ts"] and r["cost"] > 0:
                h = r["ts"].strftime("%Y-%m-%d %H:00")
                hist[h] = hist.get(h, 0.0) + r["cost"]
        for h, c in sorted(hist.items()):
            bar = "#" * int(c * 50)
            print(f"  {h}  ${c:>7.3f} {bar}")

    # top sessions by cost
    print("\n--- top sessions by cost ---")
    for r in sorted(rows, key=lambda x: -x["cost"])[:8]:
        d = r["ts"].strftime("%m-%d %H:%M") if r["ts"] else "?"
        print(f"  ${r['cost']:>7.3f} {d}  {r['slug']:<22} {project_short(r['project']):<24} {r['title'][:40]}")

    print_grok(grok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
