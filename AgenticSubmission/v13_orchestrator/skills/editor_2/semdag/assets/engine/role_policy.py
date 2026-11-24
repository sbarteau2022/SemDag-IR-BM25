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
        import re
        if len(values) == 1:
            packet = re.fullmatch(r"view\s*,\s*(\d+)\s*,\s*(\d+)\s*", values[0])
            if packet:
                values = ["view", packet[1], packet[2]]
            elif values[0].startswith(("edit,", "edit_lines,")):
                raise ValueError("comma-packed writes are ambiguous; supply separate positional_args elements: edit_lines, HANDLE, each code line")
        action = values[0]
        arities = {"prepare": (3, 4), "edit": (3, 4), "view": (2, 3, 4), "finalize": (3,), "status": (1, 2)}
        if action == "edit_lines":
            if len(values) < 3:
                raise ValueError("edit_lines requires a handle and explicit replacement lines")
        elif action not in arities or len(values) not in arities[action]:
            raise ValueError("invalid native positional action or field count")
        fields = dict(prepare=None, finalize=None, view=None, edit=None, status=False,
                      slot=None, remaining=None, text=None, lines=None, current_view=False, expected_view=None)
        if action == "prepare":
            fields.update(prepare=values[1], remaining=float(values[2]) if len(values)==4 else None, slot=values[-1])
        elif action == "edit_lines":
            fields.update(edit=values[1], text="\n".join(values[2:]))
        elif action == "edit":
            fields.update(edit=values[1], text=values[-1], expected_view=values[2] if len(values)==4 else None)
        elif action == "view":
            if len(values)==4:
                if not values[2].isdigit() or not values[3].isdigit():
                    raise ValueError("explicit view bounds must be numeric")
                fields.update(view=values[1],lines=values[2]+"-"+values[3])
            elif len(values)==2:
                fields.update(view="current", lines=values[1], current_view=True)
            elif values[1].isdigit() and values[2].isdigit():
                fields.update(view="current", lines=values[1]+"-"+values[2], current_view=True)
            else:
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
        if args.remaining is None:
            remaining = tx.task_remaining(repo)
            source = "baseline tag (conservative)"
        else:
            if not 0 < args.remaining <= 240:
                raise ValueError("remaining seconds must be within the four-minute limit")
            remaining, source = args.remaining, "explicit remaining"
            try:
                remaining = min(remaining, tx.task_remaining(repo))
                source = "minimum of baseline clock and explicit remaining"
            except tx.BudgetAnchorUnavailable:
                pass
        out = tx.prepare(args.prepare, remaining, repo, slot)
        out["budget_source"] = source
        return out
    if action == "finalize":
        return tx.finalize(args.finalize, repo, slot)
    if action == "edit":
        if args.text is None:
            raise ValueError("replacement text required")
        if getattr(args, "expected_view", None) is not None:
            import re
            if not re.fullmatch(r"L?\d+(?:-\d+)?", args.expected_view):
                raise ValueError("explicit edit range is invalid")
            bounds=args.expected_view.lstrip("L").split("-")
            expected=[int(bounds[0]),int(bounds[-1])]
            _,state=tx.load_handle(args.edit,repo,slot)
            if expected!=state["view"]:
                raise ValueError("edit range must equal the issued view; read/narrow first")
        return tx.edit(args.edit, args.text, repo, slot)
    import re
    if not args.lines or not re.fullmatch(r"L?\d+(?:-\d+)?", args.lines):
        raise ValueError("numbered range A-B required")
    bounds=args.lines.lstrip("L").split("-");a,b=int(bounds[0]),int(bounds[-1])
    handle=args.view
    if getattr(args, "current_view", False):
        path=tx.state_path(repo,slot)
        if not path.exists():
            raise ValueError("slot is unprepared")
        state=json.loads(path.read_text())
        if state["state"] not in ("prepared","edited"):
            raise ValueError("no active readable assignment")
        tx.check_versions(state)
        handle=state["handle"]
    _,state=tx.load_handle(handle,repo,slot)
    if state["allowed"][0] <= a <= b <= state["allowed"][1]:
        return tx.narrow(handle,a,b,repo,slot)
    return tx.read_context(handle,a,b,repo,slot)


def emit(role,out):
    """Publish real next-operation data; never execute a continuation automatically."""
    if role == "root" and out.get("ok"):
        state=out.get("state")
        if state in ("prepared","edited","applied"):
            out["candidate_applied_to_central"]=(state=="applied")
        if state == "prepared":
            out["next_actor"]="editor_"+out["slot"]
            out["root_can_edit"]=False
            out["next_reason"]="Check assignment relevance and prepare any required alternative, then delegate editing to this slot's owner. No edited candidate exists yet."
        elif state == "edited" and out.get("handle"):
            if out.get("verification_failed"):
                out["next_actor"]="editor_"+out["slot"]
                out["next_reason"]="This candidate failed verification; correct it before finalizing again."
            else:
                out["next_execution"]={"skill_name":"semdag","file_path":"scripts/finalize.py","positional_args":[out["handle"]]}
        elif state == "applied":
            out["next_tool"]="submit_patch"
            out["next_tool_arguments"]={}
    if role == "editor" and out.get("ok") and out.get("handle"):
        out["edit_prefix"]=["edit_lines",out["handle"]]
        out["edit_contract"]="Append replacement code as separate array elements, preserving spaces; never pack commas. Use the new handle after view."
    header = dict(out)
    source = header.pop("text", None) if header.get("ok") and "text" in header else None
    if source is not None:
        header["source_format"] = "numbered-python-v1"
    stream = sys.stdout if header.get("ok") else sys.stderr
    print(json.dumps(header,ensure_ascii=True,separators=(",",":")),file=stream)
    if source is not None:
        print("---BEGIN V13 SOURCE---",file=stream)
        print(source,file=stream)
        print("---END V13 SOURCE---",file=stream)
    return out


def main(role,bound_slot=None,argv=None):
    try:
        out=dispatch(role,bound_slot,list(sys.argv[1:] if argv is None else argv))
    except Exception as exc:
        out={"ok":False,"error":f"{type(exc).__name__}: {exc}"[:1800]}
    return emit(role,out)


def finalize_main(argv=None):
    """Only the root package registers this explicitly selected fixed operation."""
    try:
        values=list(sys.argv[1:] if argv is None else argv)
        if values and values[0]=="--":values=values[1:]
        if len(values)!=1:
            raise ValueError("finalize.py requires exactly one current candidate handle")
        repo=os.path.realpath(wsroot.workspace_root())
        _,state=tx.load_handle(values[0],repo)
        if state["slot"] not in ("1","2"):
            raise PermissionError("root finalizer supports only its two registered slots")
        out=tx.finalize(values[0],repo,state["slot"])
    except Exception as exc:
        out={"ok":False,"error":f"{type(exc).__name__}: {exc}"[:1800]}
    return emit("root",out)
