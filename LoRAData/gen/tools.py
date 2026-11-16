"""OpenAI-style declarations of the 9 harness tools + 3 skill tools (names/args from HARNESS_README 6.x and ADK skill_toolset)."""
def _t(name, desc, props, req):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}}
S = {"type": "string"}; I = {"type": "integer"}; B = {"type": "boolean"}
TOOLS = {t["function"]["name"]: t for t in [
    _t("run_command", "Run a shell command in /workspace via bash -c. Returns stdout, stderr and exit code.", {"command": S}, ["command"]),
    _t("read_file", "Read a file from /workspace with optional 1-indexed inclusive line range.", {"filepath": S, "start_line": I, "end_line": I}, ["filepath"]),
    _t("edit_file", "Replace old_string with new_string in an existing file. old_string must match exactly one place unless allow_multiple is true.", {"filepath": S, "old_string": S, "new_string": S, "allow_multiple": B}, ["filepath", "old_string", "new_string"]),
    _t("write_file", "Create or overwrite a file in /workspace.", {"filepath": S, "content": S}, ["filepath", "content"]),
    _t("get_status", "Return budget usage and patch status.", {}, []),
    _t("submit_patch", "Capture the git diff of /workspace as the final patch. Call once when finished.", {}, []),
    _t("get_code_neighbors", "Callers and callees of a symbol in the repository call graph.", {"node": S, "edge_type": S, "max_neighbors": I}, ["node"]),
    _t("search_similar_code", "Find graph nodes with embeddings most similar to a symbol or keyword query.", {"query": S, "k": I}, ["query"]),
    _t("get_code_subgraph", "Induced call subgraph (nodes and edges) for a list of symbols.", {"nodes": {"type": "array", "items": S}}, ["nodes"]),
    _t("load_skill", "Loads the SKILL.md instructions for a given skill.", {"skill_name": S}, ["skill_name"]),
    _t("load_skill_resource", "Loads a resource file from a skill's references/, assets/ or scripts/ directory.", {"skill_name": S, "file_path": S}, ["skill_name", "file_path"]),
    _t("run_skill_script", "Executes a script from a skill's scripts/ directory.", {"skill_name": S, "file_path": S, "args": {"type": "array", "items": S}}, ["skill_name", "file_path"]),
]}
def tools(*names):
    return [TOOLS[n] for n in names]
