use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use tree_sitter::{Node, Parser as TSParser};
use walkdir::WalkDir;

#[derive(Parser)]
#[command(name = "repo_ir", about = "Structural IR for Python repos")]
struct Cli {
    #[command(subcommand)]
    cmd: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Snapshot {
        root: PathBuf,
        #[arg(long, default_value = ".ir")]
        out_dir: PathBuf,
    },
    Analyze {
        root: PathBuf,
        #[arg(long, default_value = ".ir")]
        out_dir: PathBuf,
    },
    Decompose {
        root: PathBuf,
        #[arg(long, default_value = ".ir")]
        out_dir: PathBuf,
    },
    Context {
        root: PathBuf,
        #[arg(long, default_value = ".ir")]
        out_dir: PathBuf,
    },
}

const SKIP_DIRS: &[&str] = &[
    ".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache",
    ".tox", "dist", "build",
];

fn is_skipped(rel: &Path) -> bool {
    rel.components().any(|c| {
        let s = c.as_os_str().to_string_lossy();
        SKIP_DIRS.contains(&s.as_ref())
    })
}

fn collect_files(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for e in WalkDir::new(root).follow_links(false) {
        let e = match e {
            Ok(x) => x,
            Err(_) => continue,
        };
        if !e.file_type().is_file() {
            continue;
        }
        let p = e.path();
        let r = p.strip_prefix(root).unwrap_or(p);
        if is_skipped(r) {
            continue;
        }
        out.push(p.to_path_buf());
    }
    out.sort();
    out
}

fn sha256_bytes(b: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(b);
    h.finalize().iter().map(|b| format!("{:02x}", b)).collect()
}

fn rel(root: &Path, p: &Path) -> String {
    p.strip_prefix(root).unwrap_or(p).to_string_lossy().replace('\\', "/")
}

fn ensure_dir(d: &Path) {
    let _ = fs::create_dir_all(d);
}

#[derive(Serialize, Deserialize, Clone)]
struct SnapEntry {
    path: String,
    size: usize,
    offset: usize,
    sha256: String,
}

#[derive(Serialize, Deserialize)]
struct SnapIndex {
    root: String,
    files: usize,
    total_bytes: usize,
    box_sha256: String,
    entries: Vec<SnapEntry>,
}

fn cmd_snapshot(root: &Path, out_dir: &Path) {
    let out = if out_dir.is_absolute() { out_dir.to_path_buf() } else { root.join(out_dir) };
    ensure_dir(&out);
    let files = collect_files(root);

    let mut staged: Vec<(PathBuf, Vec<u8>)> = Vec::with_capacity(files.len());
    let mut total = 0usize;
    for p in &files {
        let b = fs::read(p).unwrap_or_default();
        total += b.len();
        staged.push((p.clone(), b));
    }

    let mut box_buf: Vec<u8> = vec![0u8; total];
    let mut entries = Vec::with_capacity(staged.len());
    let mut off = 0usize;
    for (p, b) in &staged {
        if !b.is_empty() {
            box_buf[off..off + b.len()].copy_from_slice(b);
        }
        entries.push(SnapEntry {
            path: rel(root, p),
            size: b.len(),
            offset: off,
            sha256: sha256_bytes(b),
        });
        off += b.len();
    }
    let box_sha = sha256_bytes(&box_buf);

    let box_path = out.join("snapshot.box");
    fs::write(&box_path, &box_buf).expect("write box");

    let index = SnapIndex {
        root: root.to_string_lossy().to_string(),
        files: entries.len(),
        total_bytes: total,
        box_sha256: box_sha,
        entries,
    };
    let idx_path = out.join("snapshot.index.json");
    fs::write(&idx_path, serde_json::to_string_pretty(&index).unwrap()).expect("write index");

    let receipt = serde_json::json!({
        "ok": true,
        "command": "snapshot",
        "files": index.files,
        "total_bytes": index.total_bytes,
        "box_sha256": index.box_sha256,
        "box_path": box_path.to_string_lossy(),
        "index_path": idx_path.to_string_lossy(),
    });
    println!("{}", serde_json::to_string(&receipt).unwrap());
}

// ---------- Analyze ----------

#[derive(Serialize, Clone)]
struct Flag {
    id: String,
    kind: String,
    file: String,
    line: usize,
    confidence: f64,
    evidence: String,
}

#[derive(Serialize)]
struct AnalyzeOut {
    root: String,
    files_scanned: usize,
    flag_count_key: BTreeMap<String, usize>,
    flags: Vec<Flag>,
    dependencies: Vec<String>,
}

fn parse_py(src: &str) -> Option<tree_sitter::Tree> {
    let mut parser = TSParser::new();
    parser.set_language(&tree_sitter_python::LANGUAGE.into()).ok()?;
    parser.parse(src, None)
}

fn node_text<'a>(node: Node, src: &'a [u8]) -> &'a str {
    std::str::from_utf8(&src[node.byte_range()]).unwrap_or("")
}

fn walk<F: FnMut(Node)>(node: Node, f: &mut F) {
    f(node);
    let mut c = node.walk();
    if c.goto_first_child() {
        loop {
            walk(c.node(), f);
            if !c.goto_next_sibling() {
                break;
            }
        }
    }
}

fn ts_line(node: Node) -> usize {
    node.start_position().row + 1
}

fn collect_imports(root_node: Node, src: &[u8], deps: &mut BTreeSet<String>) {
    walk(root_node, &mut |n| {
        if n.kind() == "import_statement" || n.kind() == "import_from_statement" {
            let mut inner = |x: Node| {
                if x.kind() == "dotted_name" {
                    let t = node_text(x, src);
                    if let Some(first) = t.split('.').next() {
                        if !first.is_empty() {
                            deps.insert(first.to_string());
                        }
                    }
                }
            };
            walk(n, &mut inner);
        }
    });
}

fn has_return_annotation(func_node: Node, src: &[u8]) -> bool {
    if let Some(params) = func_node.child_by_field_name("parameters") {
        let end = params.end_byte();
        let rest = &src[end..func_node.end_byte()];
        let r = std::str::from_utf8(rest).unwrap_or("");
        return r.contains("->");
    }
    let t = node_text(func_node, src);
    t.contains("->")
}

fn func_name(func_node: Node, src: &[u8]) -> String {
    if let Some(n) = func_node.child_by_field_name("name") {
        return node_text(n, src).to_string();
    }
    let mut res = String::new();
    walk(func_node, &mut |x| {
        if x.kind() == "identifier" && res.is_empty() {
            res = node_text(x, src).to_string();
        }
    });
    res
}

fn is_public(name: &str) -> bool {
    !name.starts_with('_')
}

fn mutable_default_params(func_node: Node) -> bool {
    if let Some(params) = func_node.child_by_field_name("parameters") {
        let mut found = false;
        let mut c = params.walk();
        if c.goto_first_child() {
            loop {
                let p = c.node();
                let mut inner = p.walk();
                if inner.goto_first_child() {
                    loop {
                        if inner.node().kind().contains("default") {
                            let mut d = inner.node().walk();
                            if d.goto_first_child() {
                                loop {
                                    let k = d.node().kind();
                                    if k == "list" || k == "dictionary" || k == "set"
                                        || k == "list_comprehension" || k == "dictionary_comprehension"
                                        || k == "set_comprehension" {
                                        found = true;
                                    }
                                    if !d.goto_next_sibling() {
                                        break;
                                    }
                                }
                            }
                        }
                        if !inner.goto_next_sibling() {
                            break;
                        }
                    }
                }
                if !c.goto_next_sibling() {
                    break;
                }
            }
        }
        return found;
    }
    false
}

fn analyze_file(root: &Path, path: &Path, flags: &mut Vec<Flag>, deps: &mut BTreeSet<String>) {
    let src = match fs::read_to_string(path) {
        Ok(s) => s,
        Err(_) => return,
    };
    let fpath = rel(root, path);
    let is_test = fpath.contains("test") || fpath.starts_with("tests/");
    let lines: Vec<&str> = src.lines().collect();
    let srcb = src.as_bytes();

    if let Some(tree) = parse_py(&src) {
        collect_imports(tree.root_node(), srcb, deps);

        let mut walker = |n: Node| {
            if n.kind() == "function_definition" {
                let name = func_name(n, srcb);
                if is_public(&name) && !has_return_annotation(n, srcb) {
                    flags.push(Flag {
                        id: format!("TYPE-{}", flags.len() + 1),
                        kind: "type_issue".to_string(),
                        file: fpath.clone(),
                        line: ts_line(n),
                        confidence: 0.4,
                        evidence: format!("public function `{}` lacks return annotation", name),
                    });
                }
                if mutable_default_params(n) {
                    flags.push(Flag {
                        id: format!("MUTDEF-{}", flags.len() + 1),
                        kind: "vuln_flag".to_string(),
                        file: fpath.clone(),
                        line: ts_line(n),
                        confidence: 0.75,
                        evidence: format!("mutable default argument in `{}`", name),
                    });
                }
            }
            if n.kind() == "assert_statement" && !is_test {
                flags.push(Flag {
                    id: format!("ASSERT-{}", flags.len() + 1),
                    kind: "vuln_flag".to_string(),
                    file: fpath.clone(),
                    line: ts_line(n),
                    confidence: 0.5,
                    evidence: "assert in non-test code".to_string(),
                });
            }
        };
        walk(tree.root_node(), &mut walker);
    }

    for (i, line) in lines.iter().enumerate() {
        let l = line.trim();
        let ln = i + 1;
        let lower = l.to_lowercase();
        if lower.contains("eval(") || lower.contains("exec(") {
            flags.push(Flag {
                id: format!("EVAL-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.95,
                evidence: "eval/exec usage".to_string(),
            });
        }
        if (lower.contains("os.system("))
            || (lower.contains("subprocess.") && (lower.contains("shell=true") || lower.contains("shell = true"))) {
            flags.push(Flag {
                id: format!("SHELL-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.95,
                evidence: "shell execution".to_string(),
            });
        }
        if lower.contains("pickle.load") || lower.contains("cpickle.load") || lower.contains("pickle.loads") {
            flags.push(Flag {
                id: format!("PICKLE-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.8,
                evidence: "unsafe pickle deserialization".to_string(),
            });
        }
        if lower.contains("yaml.load") && !lower.contains("safeloader") {
            flags.push(Flag {
                id: format!("YAML-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.8,
                evidence: "yaml.load without SafeLoader".to_string(),
            });
        }
        let secret_like = (lower.contains("api_key")
            || lower.contains("secret")
            || lower.contains("password")
            || lower.contains("token"))
            && (line.contains("=\"") || line.contains("='") || line.contains(": \"") || line.contains(": '"));
        if secret_like {
            flags.push(Flag {
                id: format!("SECRET-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.9,
                evidence: "possible hardcoded secret".to_string(),
            });
        }
        if lower.contains("except exception") || lower.contains("except baseexception") {
            flags.push(Flag {
                id: format!("BROAD-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.6,
                evidence: "broad exception handler".to_string(),
            });
        }
        if lower.contains(".execute(") && (line.contains("f\"") || line.contains("f'") || line.contains(" % ") || line.contains(" + ")) {
            flags.push(Flag {
                id: format!("SQLI-{}", flags.len() + 1),
                kind: "vuln_flag".to_string(),
                file: fpath.clone(),
                line: ln,
                confidence: 0.7,
                evidence: "possible SQL injection via string construction".to_string(),
            });
        }
    }
}

fn cmd_analyze(root: &Path, out_dir: &Path) {
    let out = if out_dir.is_absolute() { out_dir.to_path_buf() } else { root.join(out_dir) };
    ensure_dir(&out);
    let py_files: Vec<PathBuf> = collect_files(root)
        .into_iter()
        .filter(|p| p.extension().map(|e| e == "py").unwrap_or(false))
        .collect();

    let mut all_flags: Vec<Flag> = Vec::new();
    let mut deps: BTreeSet<String> = BTreeSet::new();
    let mut files = 0usize;
    let mut functions = 0usize;
    let mut classes = 0usize;

    for p in &py_files {
        files += 1;
        let src = fs::read_to_string(p).unwrap_or_default();
        if let Some(tree) = parse_py(&src) {
            walk(tree.root_node(), &mut |n| {
                if n.kind() == "function_definition" { functions += 1; }
                if n.kind() == "class_definition" { classes += 1; }
            });
        }
        analyze_file(root, p, &mut all_flags, &mut deps);
    }

    let mut key: BTreeMap<String, usize> = BTreeMap::new();
    key.insert("files".to_string(), files);
    key.insert("functions".to_string(), functions);
    key.insert("classes".to_string(), classes);
    key.insert("dependencies".to_string(), deps.len());
    let type_issues = all_flags.iter().filter(|f| f.kind == "type_issue").count();
    let vuln_flags = all_flags.iter().filter(|f| f.kind == "vuln_flag").count();
    key.insert("type_issues".to_string(), type_issues);
    key.insert("vuln_flags".to_string(), vuln_flags);
    key.insert("total_flags".to_string(), all_flags.len());

    let outdoc = AnalyzeOut {
        root: root.to_string_lossy().to_string(),
        files_scanned: py_files.len(),
        flag_count_key: key,
        flags: all_flags,
        dependencies: deps.into_iter().collect(),
    };
    let path = out.join("analyze.json");
    fs::write(&path, serde_json::to_string_pretty(&outdoc).unwrap()).expect("write analyze");

    let receipt = serde_json::json!({
        "ok": true,
        "command": "analyze",
        "files_scanned": outdoc.files_scanned,
        "flag_count_key": outdoc.flag_count_key,
        "out": path.to_string_lossy(),
    });
    println!("{}", serde_json::to_string(&receipt).unwrap());
}

// ---------- Decompose ----------

#[derive(Serialize)]
struct DNode {
    id: String,
    kind: String,
    path: String,
    start_line: usize,
    end_line: usize,
    name: Option<String>,
}

#[derive(Serialize)]
struct DEdge {
    from: String,
    to: String,
    kind: String,
    line: usize,
}

#[derive(Serialize)]
struct DagOut {
    root: String,
    nodes: Vec<DNode>,
    edges: Vec<DEdge>,
}

fn cmd_decompose(root: &Path, out_dir: &Path) {
    let out = if out_dir.is_absolute() { out_dir.to_path_buf() } else { root.join(out_dir) };
    ensure_dir(&out);
    let py_files: Vec<PathBuf> = collect_files(root)
        .into_iter()
        .filter(|p| p.extension().map(|e| e == "py").unwrap_or(false))
        .collect();

    let mut nodes: Vec<DNode> = Vec::new();
    let mut edges: Vec<DEdge> = Vec::new();
    let mut func_index: HashMap<String, String> = HashMap::new();
    let mut module_nodes: BTreeSet<String> = BTreeSet::new();

    for p in &py_files {
        let src = fs::read_to_string(p).unwrap_or_default();
        let fpath = rel(root, p);
        let file_id = format!("file:{}", fpath);
        nodes.push(DNode {
            id: file_id.clone(),
            kind: "file".to_string(),
            path: fpath.clone(),
            start_line: 1,
            end_line: src.lines().count().max(1),
            name: Some(fpath.clone()),
        });

        if let Some(tree) = parse_py(&src) {
            // imports -> edges to module nodes
            walk(tree.root_node(), &mut |n| {
                if n.kind() == "import_statement" || n.kind() == "import_from_statement" {
                    let mut mods = Vec::new();
                    let mut inner = |x: Node| {
                        if x.kind() == "dotted_name" {
                            mods.push(node_text(x, src.as_bytes()).to_string());
                        }
                    };
                    walk(n, &mut inner);
                    if let Some(m) = mods.first() {
                        let mod_root = m.split('.').next().unwrap_or(m).to_string();
                        let target = format!("module:{}", mod_root);
                        if module_nodes.insert(target.clone()) {
                            nodes.push(DNode {
                                id: target.clone(),
                                kind: "module".to_string(),
                                path: mod_root.clone(),
                                start_line: 0,
                                end_line: 0,
                                name: Some(mod_root),
                            });
                        }
                        edges.push(DEdge {
                            from: file_id.clone(),
                            to: target,
                            kind: "imports".to_string(),
                            line: ts_line(n),
                        });
                    }
                }
            });

            // recursive visitor for classes/functions
            fn visit(
                node: Node,
                src: &str,
                fpath: &str,
                file_id: &str,
                nodes: &mut Vec<DNode>,
                edges: &mut Vec<DEdge>,
                func_index: &mut HashMap<String, String>,
            ) {
                match node.kind() {
                    "class_definition" => {
                        let name = node
                            .child_by_field_name("name")
                            .map(|n| node_text(n, src.as_bytes()).to_string())
                            .unwrap_or_else(|| "Anonymous".to_string());
                        let id = format!("{}::{}", file_id, name);
                        nodes.push(DNode {
                            id: id.clone(),
                            kind: "class".to_string(),
                            path: fpath.to_string(),
                            start_line: ts_line(node),
                            end_line: node.end_position().row + 1,
                            name: Some(name),
                        });
                        edges.push(DEdge {
                            from: file_id.to_string(),
                            to: id.clone(),
                            kind: "contains".to_string(),
                            line: ts_line(node),
                        });
                        let mut c = node.walk();
                        if c.goto_first_child() {
                            loop {
                                visit(c.node(), src, fpath, file_id, nodes, edges, func_index);
                                if !c.goto_next_sibling() {
                                    break;
                                }
                            }
                        }
                        return;
                    }
                    "function_definition" => {
                        let name = node
                            .child_by_field_name("name")
                            .map(|n| node_text(n, src.as_bytes()).to_string())
                            .unwrap_or_else(|| "anonymous".to_string());
                        let mut parent_class: Option<String> = None;
                        let mut cur = node.parent();
                        while let Some(pr) = cur {
                            if pr.kind() == "class_definition" {
                                if let Some(cn) = pr.child_by_field_name("name") {
                                    parent_class = Some(node_text(cn, src.as_bytes()).to_string());
                                }
                                break;
                            }
                            cur = pr.parent();
                        }
                        let id = if let Some(cn) = &parent_class {
                            format!("{}::{}::{}", file_id, cn, name)
                        } else {
                            format!("{}::{}", file_id, name)
                        };
                        nodes.push(DNode {
                            id: id.clone(),
                            kind: "function".to_string(),
                            path: fpath.to_string(),
                            start_line: ts_line(node),
                            end_line: node.end_position().row + 1,
                            name: Some(name.clone()),
                        });
                        let container = if let Some(cn) = &parent_class {
                            format!("{}::{}", file_id, cn)
                        } else {
                            file_id.to_string()
                        };
                        edges.push(DEdge {
                            from: container,
                            to: id.clone(),
                            kind: "contains".to_string(),
                            line: ts_line(node),
                        });
                        func_index.insert(name, id.clone());
                        let mut c = node.walk();
                        if c.goto_first_child() {
                            loop {
                                visit(c.node(), src, fpath, file_id, nodes, edges, func_index);
                                if !c.goto_next_sibling() {
                                    break;
                                }
                            }
                        }
                        return;
                    }
                    _ => {}
                }
                let mut c = node.walk();
                if c.goto_first_child() {
                    loop {
                        visit(c.node(), src, fpath, file_id, nodes, edges, func_index);
                        if !c.goto_next_sibling() {
                            break;
                        }
                    }
                }
            }
            visit(tree.root_node(), &src, &fpath, &file_id, &mut nodes, &mut edges, &mut func_index);
        }
    }

    // call edges: re-walk each file, attribute call to nearest enclosing function, resolve by name
    for p in &py_files {
        let src = fs::read_to_string(p).unwrap_or_default();
        let fpath = rel(root, p);
        let file_id = format!("file:{}", fpath);
        if let Some(tree) = parse_py(&src) {
            fn walk_calls(
                node: Node,
                src: &str,
                file_id: &str,
                current_fn: &Option<String>,
                func_index: &HashMap<String, String>,
                edges: &mut Vec<DEdge>,
            ) {
                let cf = current_fn.clone();
                if node.kind() == "function_definition" {
                    let name = node
                        .child_by_field_name("name")
                        .map(|n| node_text(n, src.as_bytes()).to_string())
                        .unwrap_or_default();
                    // reconstruct id not trivial; but store current by scanning? We'll pass id via parent? Simpler: leave current_fn as previous; instead resolve container at leaf. To keep simpler, compute enclosing function id by walking up outside recursion is hard. We'll set cf to function node's "name-only" and later map? 
                    // For edges we need caller id; instead compute caller id inside call handling using parent chain. We'll handle below without cf.
                    let _ = name;
                }
                if node.kind() == "call" {
                    // callee name
                    let callee = node
                        .child(0)
                        .map(|n| node_text(n, src.as_bytes()).to_string())
                        .unwrap_or_default();
                    // simple name (last segment)
                    let simple = callee.rsplit('.').next().unwrap_or(&callee).to_string();
                    if let Some(target) = func_index.get(&simple) {
                        // find enclosing function id by walking up from node
                        let mut caller: Option<String> = None;
                        let mut cur = node.parent();
                        while let Some(pr) = cur {
                            if pr.kind() == "function_definition" {
                                if let Some(nm) = pr.child_by_field_name("name") {
                                    let fnname = node_text(nm, src.as_bytes()).to_string();
                                    let mut pc: Option<String> = None;
                                    let mut cur2 = pr.parent();
                                    while let Some(pp) = cur2 {
                                        if pp.kind() == "class_definition" {
                                            if let Some(cn) = pp.child_by_field_name("name") {
                                                pc = Some(node_text(cn, src.as_bytes()).to_string());
                                            }
                                            break;
                                        }
                                        cur2 = pp.parent();
                                    }
                                    let cid = if let Some(cn) = pc {
                                        format!("{}::{}::{}", file_id, cn, fnname)
                                    } else {
                                        format!("{}::{}", file_id, fnname)
                                    };
                                    caller = Some(cid);
                                }
                                break;
                            }
                            cur = pr.parent();
                        }
                        if let Some(caller_id) = caller {
                            if caller_id != *target {
                                edges.push(DEdge {
                                    from: caller_id,
                                    to: target.clone(),
                                    kind: "calls".to_string(),
                                    line: ts_line(node),
                                });
                            }
                        }
                    }
                }
                let mut c = node.walk();
                if c.goto_first_child() {
                    loop {
                        walk_calls(c.node(), src, file_id, &cf, func_index, edges);
                        if !c.goto_next_sibling() {
                            break;
                        }
                    }
                }
            }
            walk_calls(tree.root_node(), &src, &file_id, &None, &func_index, &mut edges);
        }
    }

    // dedup edges
    let mut seen: BTreeSet<(String, String, String, usize)> = BTreeSet::new();
    edges.retain(|e| seen.insert((e.from.clone(), e.to.clone(), e.kind.clone(), e.line)));

    let outdoc = DagOut {
        root: root.to_string_lossy().to_string(),
        nodes,
        edges,
    };
    let path = out.join("decompose.json");
    fs::write(&path, serde_json::to_string(&outdoc).unwrap()).expect("write dag");

    let receipt = serde_json::json!({
        "ok": true,
        "command": "decompose",
        "nodes": outdoc.nodes.len(),
        "edges": outdoc.edges.len(),
        "out": path.to_string_lossy(),
    });
    println!("{}", serde_json::to_string(&receipt).unwrap());
}


// ---------- Context score (uncalibrated reachability-conditioned ranking) ----------

#[derive(Serialize, Clone)]
struct FnNode {
    id: String,
    file: String,
    name: String,
    class: Option<String>,
    start_line: usize,
    end_line: usize,
    params: String,
    source_like: bool,
}

#[derive(Serialize, Clone)]
struct ContextVuln {
    #[serde(flatten)]
    flag: Flag,
    function_node: Option<String>,
    reachable_from_source: bool,
    reachability_paths: Vec<Vec<String>>,
    contextual_probability: f64,
    contextual_score: f64,
    score_kind: String,
    needed_closures: Vec<String>,
    closure_review_candidates: Vec<String>,
    related_holes: Vec<String>,
}

#[derive(Serialize)]
struct ContextOut {
    root: String,
    sources: Vec<String>,
    nodes: usize,
    vulnerable_flags: Vec<ContextVuln>,
    contextual_flag_count_key: BTreeMap<String, usize>,
}

fn is_source_name(name: &str, _file: &str, _params: &str) -> bool {
    let lower = name.to_lowercase();
    matches!(lower.as_str(), "main" | "cli" | "request" | "handle_request" | "wsgi_app" | "asgi_app" | "serve_forever")
        || ["handle_", "route_", "endpoint_"].iter().any(|prefix| lower.starts_with(prefix))
}

fn is_mitigator_text(s: &str) -> bool {
    let l = s.to_lowercase();
    ["validate","sanitize","escape","check","auth","permission","verify","authorize","whitelist","clean","guard","sanitize"].iter().any(|k| l.contains(k))
}

fn cmd_context(root: &Path, out_dir: &Path) {
    let out = if out_dir.is_absolute() { out_dir.to_path_buf() } else { root.join(out_dir) };
    ensure_dir(&out);

    let py_files: Vec<PathBuf> = collect_files(root)
        .into_iter()
        .filter(|p| p.extension().map(|e| e == "py").unwrap_or(false))
        .collect();

    // Build function nodes (macro/micro)
    let mut fn_nodes: Vec<FnNode> = Vec::new();
    let mut call_edges: Vec<(String,String)> = Vec::new();

    for p in &py_files {
        let src = fs::read_to_string(p).unwrap_or_default();
        let fpath = rel(root, p);
        let file_id = format!("file:{}", fpath);
        if let Some(tree) = parse_py(&src) {
            // recursive visitor
            fn visit(
                node: Node,
                src: &str,
                fpath: &str,
                file_id: &str,
                fn_nodes: &mut Vec<FnNode>,
            ) {
                match node.kind() {
                    "class_definition" => {
                        let mut c = node.walk();
                        if c.goto_first_child() {
                            loop {
                                visit(c.node(), src, fpath, file_id, fn_nodes);
                                if !c.goto_next_sibling() { break; }
                            }
                        }
                        return;
                    }
                    "function_definition" => {
                        let name = node
                            .child_by_field_name("name")
                            .map(|n| node_text(n, src.as_bytes()).to_string())
                            .unwrap_or_else(|| "anonymous".to_string());
                        let mut parent_class: Option<String> = None;
                        let mut cur = node.parent();
                        while let Some(pr) = cur {
                            if pr.kind() == "class_definition" {
                                if let Some(cn) = pr.child_by_field_name("name") {
                                    parent_class = Some(node_text(cn, src.as_bytes()).to_string());
                                }
                                break;
                            }
                            cur = pr.parent();
                        }
                        let id = if let Some(cn) = &parent_class {
                            format!("{}::{}::{}", file_id, cn, name)
                        } else {
                            format!("{}::{}", file_id, name)
                        };
                        let params = node.child_by_field_name("parameters").map(|n| node_text(n, src.as_bytes()).to_string()).unwrap_or_default();
                        let src_like = is_source_name(&name, &fpath, &params);
                        let fnn = FnNode {
                            id: id.clone(),
                            file: fpath.to_string(),
                            name: name.clone(),
                            class: parent_class,
                            start_line: ts_line(node),
                            end_line: node.end_position().row + 1,
                            params,
                            source_like: src_like,
                        };
                        fn_nodes.push(fnn);
                        // recurse nested
                        let mut c = node.walk();
                        if c.goto_first_child() {
                            loop {
                                visit(c.node(), src, fpath, file_id, fn_nodes);
                                if !c.goto_next_sibling() { break; }
                            }
                        }
                        return;
                    }
                    _ => {}
                }
                let mut c = node.walk();
                if c.goto_first_child() {
                    loop {
                        visit(c.node(), src, fpath, file_id, fn_nodes);
                        if !c.goto_next_sibling() { break; }
                    }
                }
            }
            visit(tree.root_node(), &src, &fpath, &file_id, &mut fn_nodes);
        }
    }

    // Resolve only calls whose lexical target is unambiguous in this file.
    let fn_ids: BTreeSet<String> = fn_nodes.iter().map(|n| n.id.clone()).collect();
    for p in &py_files {
        let src = fs::read_to_string(p).unwrap_or_default();
        let fpath = rel(root, p);
        let file_id = format!("file:{}", fpath);
        if let Some(tree) = parse_py(&src) {
            // recursive
            fn walkc(
                node: Node,
                src: &str,
                file_id: &str,
                fn_ids: &BTreeSet<String>,
                edges: &mut Vec<(String,String)>,
            ) {
                if node.kind() == "call" {
                    let callee_txt = node.child(0).map(|n| node_text(n, src.as_bytes()).to_string()).unwrap_or_default();
                    // caller enclosing function
                    let mut caller_id: Option<String> = None;
                    let mut caller_class: Option<String> = None;
                    let mut cur = node.parent();
                    while let Some(pr) = cur {
                        if pr.kind() == "function_definition" {
                            // reconstruct id using parent class
                            let pname = pr.child_by_field_name("name").map(|n| node_text(n, src.as_bytes()).to_string()).unwrap_or_default();
                            let mut pc: Option<String> = None;
                            let mut cur2 = pr.parent();
                            while let Some(pp) = cur2 {
                                if pp.kind() == "class_definition" {
                                    if let Some(cn) = pp.child_by_field_name("name") {
                                        pc = Some(node_text(cn, src.as_bytes()).to_string());
                                    }
                                    break;
                                }
                                cur2 = pp.parent();
                            }
                            caller_class = pc.clone();
                            caller_id = Some(if let Some(cn)=pc { format!("{}::{}::{}", file_id, cn, pname) } else { format!("{}::{}", file_id, pname) });
                            break;
                        }
                        cur = pr.parent();
                    }
                    let target = if let Some(method) = callee_txt.strip_prefix("self.").or_else(|| callee_txt.strip_prefix("cls.")) {
                        caller_class.as_ref().map(|class| format!("{}::{}::{}", file_id, class, method))
                    } else if !callee_txt.contains('.') && !callee_txt.is_empty() {
                        Some(format!("{}::{}", file_id, callee_txt))
                    } else {
                        None
                    };
                    if let (Some(caller), Some(target)) = (caller_id, target) {
                        if target != caller && fn_ids.contains(&target) {
                            edges.push((caller, target));
                        }
                    }
                }
                let mut c = node.walk();
                if c.goto_first_child() {
                    loop {
                        walkc(c.node(), src, file_id, fn_ids, edges);
                        if !c.goto_next_sibling() { break; }
                    }
                }
            }
            walkc(tree.root_node(), &src, &file_id, &fn_ids, &mut call_edges);
        }
    }

    // dedup
    let mut seen_edges: BTreeSet<(String,String)> = BTreeSet::new();
    call_edges.retain(|e| seen_edges.insert(e.clone()));

    // adjacency
    let mut radj: HashMap<String, Vec<String>> = HashMap::new();
    for (a,b) in &call_edges {
        radj.entry(b.clone()).or_default().push(a.clone());
    }

    // run analyze to get flags
    let mut all_flags: Vec<Flag> = Vec::new();
    let mut deps: BTreeSet<String> = BTreeSet::new();
    for p in &py_files {
        analyze_file(root, p, &mut all_flags, &mut deps);
    }

    // map flag -> innermost containing function; a file-only match is not evidence.
    let flag_node = |f: &Flag| -> Option<String> {
        fn_nodes.iter()
            .filter(|n| n.file == f.file && f.line >= n.start_line && f.line <= n.end_line)
            .min_by_key(|n| n.end_line - n.start_line)
            .map(|n| n.id.clone())
    };

    // A zero-in-degree function is not necessarily an external entry point.
    let sources: Vec<String> = fn_nodes.iter()
        .filter(|n| n.source_like)
        .map(|n| n.id.clone())
        .collect();

    let bfs_path = |target: &str| -> (bool, Vec<Vec<String>>) {
        let mut paths: Vec<Vec<String>> = Vec::new();
        // reverse BFS from target over predecessors
        let mut visited: BTreeSet<String> = BTreeSet::new();
        let mut parent: HashMap<String, Option<String>> = HashMap::new();
        let mut queue: Vec<String> = vec![target.to_string()];
        visited.insert(target.to_string());
        parent.insert(target.to_string(), None);
        while !queue.is_empty() {
            let mut next = Vec::new();
            for cur in &queue {
                if let Some(preds) = radj.get(cur) {
                    for pr in preds {
                        if !visited.contains(pr) {
                            visited.insert(pr.clone());
                            parent.insert(pr.clone(), Some(cur.clone()));
                            next.push(pr.clone());
                        }
                    }
                }
            }
            queue = next;
        }
        for src in &sources {
            if visited.contains(src) {
                let mut path = Vec::new();
                let mut cur = Some(src.clone());
                while let Some(c) = cur {
                    path.push(c.clone());
                    cur = parent.get(&c).cloned().flatten();
                }
                if path.last().map(|x| x==target).unwrap_or(false) {
                    paths.push(path);
                }
            }
        }
        let reachable = !paths.is_empty();
        paths.sort_by(|a, b| a.len().cmp(&b.len()).then_with(|| a.cmp(b)));
        paths.truncate(3);
        (reachable, paths)
    };

    // mit locations along path
    let mitigators_on_path = |path: &Vec<String>| -> bool {
        path.iter().any(|id| {
            // node calls mitigator? We don't store call names, but check node params/name/id for mitigator words
            if is_mitigator_text(id) { return true; }
            if let Some(n) = fn_nodes.iter().find(|x| x.id==*id) {
                if is_mitigator_text(&n.name) { return true; }
                // maybe params
                if is_mitigator_text(&n.params) { return true; }
            }
            false
        })
    };

    // known mitigator presence via edges? We don't track; use heuristic on id only.

    let mut vulns_out: Vec<ContextVuln> = Vec::new();
    // track which nodes are on any reachable vuln path
    let mut risky_nodes: BTreeSet<String> = BTreeSet::new();

    for f in &all_flags {
        if f.kind != "vuln_flag" { continue; }
        let node = flag_node(f);
        let (reachable, paths) = if let Some(n) = &node {
            bfs_path(n)
        } else {
            (false, vec![])
        };
        for pth in &paths {
            for id in pth { risky_nodes.insert(id.clone()); }
        }
        // Path membership suggests review sites; names cannot prove a missing gate.
        let mut review_candidates: Vec<String> = Vec::new();
        for pth in &paths {
            for id in pth {
                if !is_mitigator_text(id) {
                    if let Some(n) = fn_nodes.iter().find(|x| x.id==*id) {
                        if !is_mitigator_text(&n.name) {
                            review_candidates.push(format!("Review input validation / authorization at {} ({}:{})", n.id, n.file, n.start_line));
                        }
                    }
                }
            }
        }
        // dedup review sites
        let mut seen_c: BTreeSet<String> = BTreeSet::new();
        review_candidates.retain(|c| seen_c.insert(c.clone()));

        // base confidence
        let mut prob = f.confidence;
        if reachable {
            prob = (prob * 1.25).min(0.999);
            // if no mitigator on any path, higher
            let any_mit = paths.iter().any(|p| mitigators_on_path(p));
            if !any_mit {
                prob = (prob * 1.1).min(0.999);
            }
        }

        let score = (prob*1000.0).round()/1000.0;
        vulns_out.push(ContextVuln {
            flag: f.clone(),
            function_node: node,
            reachable_from_source: reachable,
            reachability_paths: paths,
            contextual_probability: score,
            contextual_score: score,
            score_kind: "uncalibrated_heuristic".to_string(),
            needed_closures: Vec::new(),
            closure_review_candidates: review_candidates,
            related_holes: Vec::new(),
        });
    }

    // Resolve related flags after all paths are known, independent of scan order.
    let node_by_flag: HashMap<String, Option<String>> = vulns_out.iter()
        .map(|v| (v.flag.id.clone(), v.function_node.clone()))
        .collect();
    for v in &mut vulns_out {
        v.related_holes = all_flags.iter()
            .filter(|g| g.kind == "vuln_flag" && g.id != v.flag.id &&
                (g.file == v.flag.file || node_by_flag.get(&g.id).and_then(|n| n.as_ref()).map(|n| risky_nodes.contains(n)).unwrap_or(false)))
            .map(|g| g.id.clone())
            .collect();
    }

    // contextual count key
    let mut key: BTreeMap<String, usize> = BTreeMap::new();
    key.insert("functions".to_string(), fn_nodes.len());
    key.insert("sources".to_string(), sources.len());
    key.insert("vuln_flags".to_string(), vulns_out.len());
    key.insert("reachable_vulns".to_string(), vulns_out.iter().filter(|v| v.reachable_from_source).count());
    key.insert("needed_closures".to_string(), vulns_out.iter().map(|v| v.needed_closures.len()).sum());
    key.insert("closure_review_candidates".to_string(), vulns_out.iter().map(|v| v.closure_review_candidates.len()).sum());

    let outdoc = ContextOut {
        root: root.to_string_lossy().to_string(),
        sources,
        nodes: fn_nodes.len(),
        vulnerable_flags: vulns_out,
        contextual_flag_count_key: key,
    };
    let path = out.join("context_prob.json");
    fs::write(&path, serde_json::to_string_pretty(&outdoc).unwrap()).expect("write context");

    let receipt = serde_json::json!({
        "ok": true,
        "command": "context",
        "nodes": outdoc.nodes,
        "sources": outdoc.sources.len(),
        "vulns": outdoc.vulnerable_flags.len(),
        "reachable_vulns": outdoc.contextual_flag_count_key.get("reachable_vulns"),
        "out": path.to_string_lossy(),
    });
    println!("{}", serde_json::to_string(&receipt).unwrap());
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        Commands::Snapshot { root, out_dir } => cmd_snapshot(&root, &out_dir),
        Commands::Analyze { root, out_dir } => cmd_analyze(&root, &out_dir),
        Commands::Decompose { root, out_dir } => cmd_decompose(&root, &out_dir),
        Commands::Context { root, out_dir } => cmd_context(&root, &out_dir),
    }
}
