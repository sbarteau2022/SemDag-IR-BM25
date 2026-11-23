"""flow: the recurrent structure of one function, read from the hybrid SemDAG graph.

For a function or method it reports, compactly:
  loops      each loop in it: kind, lines, nesting depth, loop-carried names, exits, and what
             the loop body calls (from `loop_calls`)
  recursion  whether it sits in a call cycle, and the other members of that cycle
  callers    who calls or instantiates it (inverse edges), library first
  callees    what it calls outside its loops
  topo_rank  its place in the condensed call order (lower calls higher)
"""
from collections import defaultdict

import retriever

MAX_LOOPS, MAX_CALLS, MAX_CALLERS, MAX_MEMBERS = 6, 5, 5, 6


class Index:
    def __init__(self, ir):
        self.nodes = {n["id"]: n for n in ir["nodes"]}
        self.out = defaultdict(lambda: defaultdict(list))
        for e in ir["edges"]:
            self.out[e["src"]][e["rel"]].append(e["dst"])
        self.by_qual = defaultdict(list)
        for n in ir["nodes"]:
            if n["kind"] in ("function", "method", "class"):
                self.by_qual[n.get("qualname", n["name"])].append(n["id"])
                self.by_qual[f"{n['file']}::{n.get('qualname', n['name'])}"].append(n["id"])

    def find(self, ref, file=None):
        """Node ids for `qualname`, `file::qualname` or a bare name; overload stubs last."""
        ids = self.by_qual.get(ref) or [i for q, v in self.by_qual.items()
                                        if "::" not in q and q.split(".")[-1] == ref for i in v]
        if file:
            ids = [i for i in ids if self.nodes[i]["file"] == file] or ids
        return sorted(set(ids), key=lambda i: (bool(self.nodes[i].get("overload")),
                                               retriever.is_test_path(self.nodes[i]["file"]), i))

    def label(self, nid):
        n = self.nodes[nid]
        if n["kind"] == "loop":
            return f"{n['file']}:{n['line']} {n['loop_kind']}"
        return f"{n['file']}:{n['line']} {n.get('qualname', n['name'])}"

    def loops_of(self, fid):
        """Loops lexically inside fid (nested loops included, nested functions excluded)."""
        found, stack = [], list(self.out[fid]["contains"])
        while stack:
            c = stack.pop()
            if self.nodes[c]["kind"] == "loop":
                found.append(c)
                stack.extend(self.out[c]["contains"])
        return sorted(found, key=lambda i: (self.nodes[i]["line"], i))

    def callers(self, fid):
        ids = set(self.out[fid]["called_by"]) | set(self.out[fid]["instantiated_by"])
        ids.discard(fid)
        lib = sorted(i for i in ids if not retriever.is_test_path(self.nodes[i]["file"]))
        tests = len(ids) - len(lib)
        return lib, tests


def site_flags(index, fid):
    """Short recurrence flags for one ranked edit site (used by repo_eval locate)."""
    n = index.nodes.get(fid, {})
    out = {}
    if n.get("loops"):
        out["loops"] = n["loops"]
    if n.get("recursive"):
        out["recursive"] = n.get("scc_size", 1)
    lib, tests = index.callers(fid) if fid in index.nodes else ([], 0)
    if lib:
        out["callers"] = [index.label(i) for i in lib[:2]]
    return out


def describe(ir, ref, file=None, index=None):
    index = index or Index(ir)
    ids = [i for i in index.find(ref, file) if index.nodes[i]["kind"] in ("function", "method", "class")]
    if not ids:
        return {"error": f"no function or class named {ref!r} in the graph",
                "hint": "Pass a qualname such as Class.method, or file.py::Class.method, from top_edit_sites."}
    fid = ids[0]
    n = index.nodes[fid]
    if n["kind"] == "class":
        init = [c for c in index.out[fid]["contains"] if index.nodes[c]["name"] == "__init__"]
        if init:
            fid, n = init[0], index.nodes[init[0]]
    loops = []
    in_loop = set()
    for lid in index.loops_of(fid)[:MAX_LOOPS]:
        l = index.nodes[lid]
        calls = sorted(set(index.out[lid]["loop_calls"]))
        in_loop.update(calls)
        loops.append({"at": f"{l['line']}-{l.get('end_line', l['line'])}", "kind": l["loop_kind"],
                      "depth": l["depth"], "carried": l.get("carried", [])[:6],
                      "exits": l.get("exits", {}), "test": l.get("test"),
                      "exit_guards": [f'{e["kind"]}@{e["line"]} if {e["cond"]}' for e in l.get("exit_conds", [])
                                      if e.get("cond")][:3],
                      "calls": [index.nodes[c].get("qualname", index.nodes[c]["name"]) for c in calls[:MAX_CALLS]]})
    callees = sorted(set(index.out[fid]["calls"]) | set(index.out[fid]["instantiates"]))
    lib, tests = index.callers(fid)
    out = {"node": index.label(fid), "end_line": n.get("end_line"), "topo_rank": n.get("topo_rank"),
           "loops": loops,
           "calls": [index.label(c) for c in callees if c not in in_loop and c != fid][:MAX_CALLS],
           "callers": [index.label(c) for c in lib[:MAX_CALLERS]], "callers_total": len(lib),
           "test_callers": tests}
    if n.get("recursive"):
        members = index.nodes[n["scc"]]["members"]
        out["recursion"] = {"cycle_size": len(members), "self_call": fid in index.out[fid]["calls"],
                            "with": [index.label(m) for m in members if m != fid][:MAX_MEMBERS]}
    if len(ids) > 1:
        out["also"] = [index.label(i) for i in ids[1:4]]
    return out
