#!/usr/bin/env python3
"""Task tracker for the Wasla delivery plan.

Source of tasks: integration/prd/04-delivery-plan.md (tables with rows "| T<phase>.<epic>.<n> | ...").
State:           progress/tasks.json (statuses and notes; never edit by hand, use this script).

Usage:
  tasks.py sync                      Re-read the plan, add/update tasks, keep statuses and notes
  tasks.py brief                     Short summary for session start
  tasks.py next [-n 5] [--all] [--any-phase]
                                     Ready tasks of the current phase (deps done).
                                     --all includes human-only tasks; --any-phase looks ahead
  tasks.py show <ID>                 Task details, dependency status, where to read
  tasks.py list [--phase N] [--status S]
  tasks.py start <ID>                Mark in_progress
  tasks.py done <ID> [--note TEXT]   Mark done
  tasks.py block <ID> --note TEXT    Mark blocked with reason
  tasks.py external <ID> [--note T]  Done outside the codebase (human/business task)
  tasks.py reopen <ID>               Back to todo
  tasks.py note <ID> --note TEXT     Append a note

Statuses: todo, in_progress, done, blocked, external, skipped.
Only the standard library is used so it runs before any project tooling exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "integration" / "prd" / "04-delivery-plan.md"
STATE = ROOT / "progress" / "tasks.json"

TASK_ROW = re.compile(r"^\|\s*(T\d+\.\d+\.\d+)\s*\|(.*)\|\s*$")
PHASE_HDR = re.compile(r"^##\s+\d+\.\s+Phase\s+(\d+)\s+—\s+(.*)$")
EPIC_HDR = re.compile(r"^###\s+(E\d+\.\d+)\s+(.*)$")
TASK_ID = re.compile(r"T\d+\.\d+\.\d+")
TASK_WILDCARD = re.compile(r"(T\d+\.\d+)\.\*")
HUMAN_ROLES = {"PM", "UX", "DOM"}
DONE_LIKE = {"done", "external", "skipped"}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_plan() -> list[dict]:
    tasks: list[dict] = []
    phase, phase_title, epic, epic_title = None, "", None, ""
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        if m := PHASE_HDR.match(line):
            phase, phase_title = int(m.group(1)), m.group(2).strip()
            continue
        if line.startswith("## ") and not PHASE_HDR.match(line):
            phase = None  # left the phase sections (backlog, workstreams, ...)
            continue
        if m := EPIC_HDR.match(line):
            epic, epic_title = m.group(1), m.group(2).strip()
            continue
        if phase is None:
            continue
        if m := TASK_ROW.match(line):
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) < 5:
                continue
            title, svc, role, pw, deps = cells[0], cells[1], cells[2], cells[3], cells[4]
            roles = {r.strip().rstrip("*") for r in role.split(",") if r.strip()}
            tasks.append({
                "id": m.group(1),
                "phase": phase,
                "phase_title": phase_title,
                "epic": epic,
                "epic_title": epic_title,
                "title": title,
                "services": svc,
                "roles": role,
                "estimate_pw": pw,
                "deps_raw": deps,
                "kind": "human" if roles and roles <= HUMAN_ROLES else "eng",
            })
    return tasks


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"version": 1, "updated_at": None, "tasks": {}}


def save_state(state: dict) -> None:
    state["updated_at"] = now()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_deps(task: dict, parsed: list[dict]) -> list[str]:
    """Explicit IDs and wildcards (T1.6.*); words: 'all'/'many' = every earlier engineering
    task of the same phase, 'above' = every earlier task of the same epic."""
    raw = task["deps_raw"]
    all_ids = [t["id"] for t in parsed]
    deps = set(TASK_ID.findall(raw))
    for prefix in TASK_WILDCARD.findall(raw):
        deps.update(i for i in all_ids if i.startswith(prefix + "."))
    words = raw.lower()
    earlier = [t for t in parsed if sort_key(t["id"]) < sort_key(task["id"])]
    if "all" in words.split() or "many" in words.split():
        deps.update(t["id"] for t in earlier if t["phase"] == task["phase"] and t["kind"] == "eng")
    if "above" in words.split():
        deps.update(t["id"] for t in earlier if t["epic"] == task["epic"])
    deps.discard(task["id"])
    return sorted(deps, key=sort_key)


def sort_key(task_id: str) -> tuple:
    return tuple(int(p) for p in task_id[1:].split("."))


def cmd_sync(_args) -> None:
    parsed = parse_plan()
    state = load_state()
    ids = [t["id"] for t in parsed]
    existing = state["tasks"]
    added = 0
    for t in parsed:
        prev = existing.get(t["id"], {})
        t["deps"] = resolve_deps(t, parsed)
        t["status"] = prev.get("status", "todo")
        t["notes"] = prev.get("notes", [])
        t["updated_at"] = prev.get("updated_at")
        if not prev:
            added += 1
        existing[t["id"]] = t
    removed = [i for i in list(existing) if i not in ids]
    for i in removed:
        existing[i]["status"] = "skipped"
        existing[i].setdefault("notes", []).append(f"{now()} removed from plan")
    save_state(state)
    print(f"synced {len(parsed)} tasks ({added} new, {len(removed)} no longer in plan)")


def get(state: dict, task_id: str) -> dict:
    t = state["tasks"].get(task_id)
    if not t:
        sys.exit(f"unknown task {task_id}; run `tasks.py sync` or check the ID")
    return t


def ready(state: dict, include_human: bool, any_phase: bool = False) -> list[dict]:
    tasks = state["tasks"]
    phase = current_phase(state)
    out = []
    for t in tasks.values():
        if t["status"] != "todo":
            continue
        if not any_phase and t["phase"] != phase:
            continue
        if t["kind"] == "human" and not include_human:
            continue
        if all(tasks.get(d, {}).get("status") in DONE_LIKE for d in t["deps"]):
            out.append(t)
    return sorted(out, key=lambda t: sort_key(t["id"]))


def current_phase(state: dict) -> int:
    open_phases = [t["phase"] for t in state["tasks"].values() if t["status"] not in DONE_LIKE]
    return min(open_phases) if open_phases else -1


def fmt(t: dict) -> str:
    return f"{t['id']} [{t['status']}] ({t['kind']}, {t['services']}, {t['roles']}, {t['estimate_pw']}pw) {t['title']}"


def cmd_brief(_args) -> None:
    state = load_state()
    if not state["tasks"]:
        print("No tasks tracked yet. Run: python3 tools/progress/tasks.py sync")
        return
    tasks = state["tasks"].values()
    phase = current_phase(state)
    counts: dict[str, int] = {}
    for t in tasks:
        if t["phase"] == phase:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
    print(f"Current phase: {phase} — " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    active = [t for t in tasks if t["status"] in ("in_progress", "blocked")]
    if active:
        print("In progress / blocked:")
        for t in sorted(active, key=lambda t: sort_key(t["id"])):
            last = t["notes"][-1] if t["notes"] else ""
            print(f"  {fmt(t)}" + (f"\n      last note: {last}" if last else ""))
    nxt = ready(state, include_human=False)[:5]
    if nxt:
        print("Next ready engineering tasks:")
        for t in nxt:
            print(f"  {fmt(t)}")
    human = ready(state, include_human=True)
    human = [t for t in human if t["kind"] == "human"][:3]
    if human:
        print("Open human/business tasks (mark with `external` when done outside the code):")
        for t in human:
            print(f"  {fmt(t)}")


def cmd_next(args) -> None:
    for t in ready(load_state(), args.all, args.any_phase)[: args.n]:
        print(fmt(t))


def cmd_show(args) -> None:
    state = load_state()
    t = get(state, args.id)
    print(fmt(t))
    print(f"Phase {t['phase']}: {t['phase_title']}")
    print(f"Epic {t['epic']}: {t['epic_title']}")
    print(f"Dependencies (raw): {t['deps_raw']}")
    for d in t["deps"]:
        dt_ = state["tasks"].get(d)
        print(f"  {d}: {dt_['status'] if dt_ else 'unknown'}" + (f" — {dt_['title']}" if dt_ else ""))
    if t["notes"]:
        print("Notes:")
        for n in t["notes"]:
            print(f"  {n}")
    svc = re.findall(r"S\d{2}", t["services"])
    print("Read: integration/prd/04-delivery-plan.md (task row + epic)")
    if svc:
        print("      integration/prd/03-services.md sections: " + ", ".join(svc))
    print("      integration/prd/05-tech-stack.md (deployable + libraries), 02-architecture.md (relevant flow)")


def cmd_list(args) -> None:
    state = load_state()
    for t in sorted(state["tasks"].values(), key=lambda t: sort_key(t["id"])):
        if args.phase is not None and t["phase"] != args.phase:
            continue
        if args.status and t["status"] != args.status:
            continue
        print(fmt(t))


def set_status(task_id: str, status: str, note: str | None) -> None:
    state = load_state()
    t = get(state, task_id)
    t["status"] = status
    t["updated_at"] = now()
    if note:
        t.setdefault("notes", []).append(f"{now()} {status}: {note}")
    save_state(state)
    print(fmt(t))


def main() -> None:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    sub.add_parser("brief").set_defaults(fn=cmd_brief)
    n = sub.add_parser("next"); n.add_argument("-n", type=int, default=5); n.add_argument("--all", action="store_true"); n.add_argument("--any-phase", action="store_true"); n.set_defaults(fn=cmd_next)
    s = sub.add_parser("show"); s.add_argument("id"); s.set_defaults(fn=cmd_show)
    ls = sub.add_parser("list"); ls.add_argument("--phase", type=int); ls.add_argument("--status"); ls.set_defaults(fn=cmd_list)
    for name, status in [("start", "in_progress"), ("done", "done"), ("block", "blocked"),
                         ("external", "external"), ("reopen", "todo"), ("skip", "skipped")]:
        c = sub.add_parser(name); c.add_argument("id"); c.add_argument("--note")
        c.set_defaults(fn=lambda a, st=status: set_status(a.id, st, a.note))
    nt = sub.add_parser("note"); nt.add_argument("id"); nt.add_argument("--note", required=True)
    nt.set_defaults(fn=lambda a: set_status(a.id, get(load_state(), a.id)["status"], a.note))
    args = p.parse_args()
    if args.cmd == "block" and not args.note:
        sys.exit("block requires --note with the reason")
    args.fn(args)


if __name__ == "__main__":
    main()
