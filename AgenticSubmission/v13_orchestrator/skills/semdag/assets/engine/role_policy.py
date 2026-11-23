"""Role-bound action authorization; role and slot are fixed by registered entry code."""
import argparse
import json
import os
import sys

import edit_tx as tx
import wsroot

CAPABILITIES = {
    "root": frozenset(("prepare", "finalize", "status")),
    "editor": frozenset(("view", "edit", "status")),
}


def dispatch(role, bound_slot, argv):
    if role not in CAPABILITIES or (role == "editor" and bound_slot not in ("1", "2")):
        raise ValueError("invalid static role binding")
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--prepare")
    actions.add_argument("--finalize")
    actions.add_argument("--view")
    actions.add_argument("--edit")
    actions.add_argument("--status", action="store_true")
    parser.add_argument("--slot", choices=("1", "2"))
    parser.add_argument("--remaining", type=float)
    parser.add_argument("--text")
    parser.add_argument("--lines")
    # Accept an explicit JSON array serialized as one argv value. No fields,
    # actions or roles are inferred, and outer SDK arguments are not rewritten.
    if len(argv) == 1 and argv[0].lstrip().startswith("["):
        decoded = json.loads(argv[0])
        if not isinstance(decoded, list) or not all(isinstance(v, str) for v in decoded):
            raise ValueError("serialized arguments must be a JSON array of strings")
        argv = decoded
    if argv and argv[0] == "--":
        # This delimiter is inserted by the unmodified SDK for positional_args.
        values = argv[1:]
        if not values:
            raise ValueError("native action required")
        action = values[0]
        arities = {"prepare": (4,), "edit": (3,), "view": (3,), "finalize": (3,), "status": (1, 2)}
        if action not in arities or len(values) not in arities[action]:
            raise ValueError("invalid native positional action or field count")
        fields = dict(prepare=None, finalize=None, view=None, edit=None, status=False,
                      slot=None, remaining=None, text=None, lines=None)
        if action == "prepare":
            fields.update(prepare=values[1], remaining=float(values[2]), slot=values[3])
        elif action == "edit":
            fields.update(edit=values[1], text=values[2])
        elif action == "view":
            fields.update(view=values[1], lines=values[2])
        elif action == "finalize":
            fields.update(finalize=values[1], slot=values[2])
        else:
            fields.update(status=True, slot=values[1] if len(values) == 2 else None)
        args = argparse.Namespace(**fields)
        if args.slot is not None and args.slot not in ("1", "2"):
            raise ValueError("invalid native slot")
    else:
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            raise ValueError("invalid native action arguments") from exc
    action = next(k for k in ("prepare", "finalize", "view", "edit", "status")
                  if getattr(args, k) is not None and getattr(args, k) is not False)
    if action not in CAPABILITIES[role]:
        raise PermissionError(f"{role} cannot perform {action}")
    slot = args.slot or bound_slot or "1"
    if role == "editor" and slot != bound_slot:
        raise PermissionError("editor cannot access another slot")
    repo = os.path.realpath(wsroot.workspace_root())  # Never accept a model-supplied host repo path.
    if action == "status":
        path = tx.state_path(repo, slot)
        if not path.exists():
            return {"ok": False, "state": "unprepared", "slot": slot,
                    "next": ("Prepare this slot with the issue and remaining budget before dispatching an editor." if role == "root" else
                             "Return EDIT_FAILED: root did not prepare this slot. Do not retry or list skills.")}
        state = json.loads(path.read_text())
        if state["repo"] != repo or state["slot"] != slot:
            raise ValueError("assignment identity mismatch")
        if state["state"] in ("applied", "failed"):
            return {"ok": True, "state": state["state"], "slot": slot}
        tx.check_versions(state)
        return {**tx.view_result(state), "state": state["state"]}
    if action == "prepare":
        if args.remaining is None or not 0 < args.remaining <= 240:
            raise ValueError("remaining seconds from get_status required (0 < seconds <= 240)")
        return tx.prepare(args.prepare, args.remaining, repo, slot)
    if action == "finalize":
        return tx.finalize(args.finalize, repo, slot)
    if action == "edit":
        if args.text is None:
            raise ValueError("replacement text required")
        return tx.edit(args.edit, args.text, repo, slot)
    import re
    if not args.lines or not re.fullmatch(r"L?\d+-\d+", args.lines):
        raise ValueError("numbered range A-B required")
    a,b = map(int,args.lines.lstrip("L").split("-"))
    return tx.narrow(args.view,a,b,repo,slot)


def main(role, bound_slot=None, argv=None):
    try:
        out = dispatch(role, bound_slot, list(sys.argv[1:] if argv is None else argv))
    except Exception as exc:
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:1800]}
    print(json.dumps(out,ensure_ascii=False,separators=(",",":")))
    return out
