---
title: "Subspace-Coordinated Sparse LoRA Bank for Gemma 4 Agent Specialization"
document_type: "architecture"
version: "0.3.0"
date: "2026-11-11T00:00:00Z"
implementation_date: null
author: "Codex"
reviewers: []
status: "draft"
related_files:
  - path: "Designs/SharedLoRABank/design.md"
    lines: "1-754"
    role: "primary"
  - path: "Designs/SharedLoRABank/README.md"
    lines: "1-117"
    role: "supporting"
related_issues: []
related_documents:
  - "../Paperwork/Plan_of_Attack.md"
  - "obsidian-4d-observer.md"
  - "../../Rules/Overview/Model_Choice.md"
  - "../../DataSets/public/HARNESS_README.md"
tags: ["gemma-4", "lora", "model-merging", "sparse-adapters", "multi-agent", "paper-track"]
---

# Executive Summary

**[PROPOSED]** First map recurring, causally useful computation during coding tasks in frozen Gemma 4 E4B. Then test whether a coordinated bank of low-rank update atoms can steer those operations through sparse role gates. Compile each admitted view into an ordinary PEFT LoRA adapter so the competition runtime retains one legal base model.

**[PROPOSED]** The research contribution is not “more agents.” It is a factorization-invariant method for discovering, allocating, measuring, and composing role-specific parameter subspaces while minimizing destructive interference. The deployment claim remains unproven until held-out repository evaluation shows improved resolved-task count or a pre-registered efficiency/quality advantage.

# Problem Statement

**[VERIFIED: SRC-01, SRC-02]** The competition permits one declared base model across the complete agent hierarchy and permits different LoRA adapters on different agents. The harness routes an adapter name to a served model alias while preserving the single canonical base-model declaration.

**[INFERRED: SRC-01, SRC-02]** Independently trained role LoRAs may duplicate capabilities, learn incompatible parameter directions, and provide no principled account of which frozen-model subspaces each role uses. This inference ends before any claim that independent adapters are empirically worse on Gemma 4 E4B; that comparison has not run.

**[REPORTED: SRC-04–SRC-11]** Prior work shows that low-rank updates can be composed, that weight-space interference matters, that sparsifying or sign-resolving task deltas can improve some merges, and that shared/canonical low-dimensional coordinates can improve parameter-efficient fusion. The literature does not establish that strict orthogonality alone creates semantically composable capabilities.

# Research Question and Decision Unblocked

**[PROPOSED]** Research question: can a shared rank-atom bank with learned sparse role gates preserve or improve specialist patching behavior while reducing measured overlap and improving adapter composition relative to independently trained LoRAs?

**[PROPOSED]** This design unblocks whether to allocate Kaggle L4x4 training time to a coordinated adapter family and whether that family is strong enough for the main submission, the Small Model track, or a paper-only contribution.

## Separate hypotheses

**[PROPOSED] H1 — engineering:** Under matched training and served-rank budgets, a coordinated sparse bank improves held-out patch resolution compared with independent LoRAs. Lower aggregate adapter storage is a separate conditional claim that requires measured exported bytes and loader support for the declared rank profile.

**[PROPOSED] H2 — mechanistic:** Role gates preferentially control causally distinct computation already available in the frozen base. H2 is strictly stronger than H1. Better patches, sparse gates, low delta cosine, or clean merges do not prove H2; selective causal intervention must outperform matched random and norm-matched controls.

**[PROPOSED] Null interpretation:** The bank may merely learn an efficient coordinate system for external weight updates. If H1 passes and H2 fails, describe the result as coordinated parameter-efficient adaptation, not discovery or activation of latent subnetworks.

# Prior Carved-Swarm Evidence and Transfer Boundary

**[VERIFIED: SRC-16, SRC-17]** The earlier Muse Glimmer carved-swarm demo used one frozen weight set for four scoped workers and a lead. Its recorded run answered 3/4 own-view questions and 3/4 union-view questions; the four cross-view questions were not answerable from the workers' scoped recalled atoms. A separate six-fact test recorded 5/6 answers with a matched recalled atom, 0/6 without one, and 1/6 with a mismatched atom. These are small local component tests, not Gemma 4 or LoRA results.

**[INFERRED: SRC-16, SRC-17]** Those controls show that one weight set can express different observable behavior under compartmentalized information access. The evidence ends at scoped external recall and prompt context. It does not yet establish that frozen internal activation pathways are separable or that a LoRA can select them. The Glimmer result supplies a tested experimental pattern: same weights, matched prompt, own/mismatched/absent information, and a union control.

**[VERIFIED: SRC-21, SRC-22]** The carved recall contract binds a worker's well IDs to a server-held, role-bound, expiring capability and rejects missing or mismatched scope. The Whitehead Gamma-12 contract specifies twelve peer wells, an L0 coordinator, and an H3×T2 geometric frame. These are concrete scoping and representation contracts in the earlier system; they do not assert that E4B has twelve natural internal circuits.

**[REPORTED: SRC-23]** The November 4 brigade paper distinguishes seeded same-weight swarm behavior from a brigade governed by one gate and receipt ledger. Its 9/10 prompt-seeded combination result and its own attestation limitation cannot be imported as an E4B adapter score. The useful transfer is its discipline: one declared scope, independent outcome checks, and receipts before confidence updates.

**[PROPOSED]** Transfer that pattern to E4B: hold the frozen weights, input format, output budget, and task fixed; vary only a scoped information view or a reversible activation intervention. Record both behavior and internal trajectories. Before LoRA training, determine whether the view changes a repeatable causal pathway rather than merely adding answer text to context. Glimmer is prior evidence for the method and is never a second model in the competition submission.

# Computation Ontology and Basin Hypothesis

**[PROPOSED]** Observe this program through the time-indexed relational graph in [`obsidian-4d-observer.md`](obsidian-4d-observer.md). It records what was activated, where, under which task and intervention, and how behavior changed. Obsidian is the review surface; immutable experiment records remain the evidence source. A graph edge is a hypothesis until its receipt supports the stated causal or correlational status.

**[PROPOSED]** Search for operations needed by coding work rather than programming-language labels: token and grammar constraints; symbol binding; control and data-flow tracking; API contract retrieval; counterexample search; edit planning; and verification. These are experimental probes, not assumed neuron locations or benchmark-provided role labels. A routing role may combine several operations, and one operation may be distributed across layers, token positions, and modules.

**[PROPOSED]** The “twelve around one” structure is a candidate organization: twelve specialist views around a shared coordinating view, with shared and role-specific overlap. Test this cardinality against smaller and data-selected counts under the same budget; the geometric analogy does not by itself force twelve E4B circuits.

**[PROPOSED]** A Whitehead-style H3×T2 map may be one candidate embedding of E4B activation trajectories. Fit it only on the training partition and compare with Euclidean, randomized-well, and unconstrained clustering controls for held-out recurrence and causal selectivity. The Gamma-12 quotient is a prior geometric contract, not a discovered E4B topology. A central view may aggregate admitted specialists; it must not silently bypass their scope boundaries.

**[PROPOSED]** Operationally, a candidate informational basin is a reproducible cluster of activation trajectories that (a) recurs across lexically and repository-distinct examples of an operation, (b) is more predictive of that operation than matched controls, and (c) changes the operation's behavior when intervened on. The term “basin” does not assert a literal dynamical attractor until trajectory convergence and stability are measured.

**[PROPOSED]** Construct matched counterfactual pairs from training repositories: preserve syntax while changing data-flow meaning; preserve meaning while changing names or syntax; hold code fixed while changing the required API contract; and swap relevant/irrelevant evidence at equal token length. Derive observable labels from parsing, static analysis, public tests, and audited tool traces. Record construction rules and spot-check labels. Held-out gold patches, hints, and test patches cannot enter probe design or training.

**[PROPOSED: SRC-19]** Capture layer- and token-position activations and attention outputs on the frozen E4B checkpoint. Rank candidate directions or groups by cross-validated selectivity and recurrence across task families, then perform activation patching, targeted ablation, and matched random or norm-matched interventions. Measure behavioral loss, collateral loss, and recovery by restoring the component. The experiment must include lexical decoys so a feature responding to words like “reason” or “Python” cannot masquerade as an operation detector.

**[PROPOSED: SRC-18]** Repeated activation updates a hypothesis about participation; low measured activity alone does not license pruning. A low-salience component can carry inhibitory, indirect, or context-specific information. Prune only after an intervention shows preserved coding accuracy and acceptable collateral behavior under a named budget. Layer redundancy studies motivate this test, but their retention numbers do not transfer to E4B or this task set without measurement.

**[PROPOSED]** Criticality and pruning are two labels of one concordance procedure. Activate a site, repeat the same intervention on a fresh draw, and re-rank confidence from the agreement. Agreement on a behavioral change, followed by restoration of that behavior when the site is put back, labels the site `critical` for that operation. Agreement on a null effect, followed by a retention check that coding behavior still holds, labels the same site `unnecessary` under that budget. Low norm, a single pass, or a visual cluster assigns neither label. A refutation of the concordance procedure withdraws both labels it has already assigned. The observer validator rejects either label when its twin evidence is missing. The repeated `changes` pair must use metric `behavior_change`. The `restores` event must use metric `behavior_restored` with a non-negative value. The `retains` event must use metric `coding_accuracy_delta` with a non-negative value. Last-token logit KL, top-1 identity, hidden cosine, and activation norm cannot discharge either label.

# Pre-Registered Acceptance Criteria

**[PROPOSED]** These criteria precede implementation and results:

1. The exported artifacts validate as standard E4B PEFT LoRAs and remain below competition package limits.
2. Every competition agent declares the same E4B base model; only `adapter` differs.
3. Runtime uses one adapter alias per request; no claim depends on unsupported token-level or rank-level runtime gating.
4. Overlap metrics operate on effective deltas or their subspaces, not raw non-identifiable LoRA factors.
5. Data splits are repository-disjoint wherever the task count permits, and no held-out test patch enters training or routing selection.
6. Baseline, independent-LoRA, coordinated-dense, coordinated-sparse, and random-mask controls receive comparable training budgets.
7. Deployment requires a higher held-out resolved-task count than the current candidate it would replace, no increase in malformed/no-patch rate, and compliance with the global 12-hour inference limit.
8. A scientific result may be reported even when deployment fails, but every claim must name the run, split, seeds, and confidence interval.
9. Freeze the split, hypotheses, primary endpoint, stopping rule, and analysis manifest before revealing held-out outcomes; record its SHA-256 digest.

# Status and Decision

**[PROPOSED]** Adopt this document as a research architecture, not as an approved submission change. Do not modify `AgenticSubmission/v0_baseline` until the implementation and admission gates in this document pass.

# Terminology

| Term | Definition | Status |
|---|---|---|
| Base model | Frozen `gemma-4-e4b-it-qat-w4a16-ct`. | VERIFIED |
| Rank atom | One rank-one update \(b_k a_k^\top\) inside a target projection. | DEFINITION |
| Bank | Shared ordered collection of rank atoms across admitted target modules. | DEFINITION |
| Role gate | Sparse vector selecting and weighting bank atoms for one agent role. | DEFINITION |
| Compiled view | Ordinary LoRA factors whose effective delta equals a gated bank view. | DEFINITION |
| Adapter alias | Runtime routing identity such as `implementation`; internally resolved as a served model alias. | VERIFIED |
| Dynamic routing | Selection of rank atoms during a request based on tokens or activations. | OUT OF SCOPE |
| Latent subnetwork | A hypothesized subset of base computation preferentially influenced by an adapter view. | PROPOSED; requires causal evidence |

# Competition and Runtime Contract

## Verified constraints

**[VERIFIED: SRC-01]** The submission uses E4B for the root and every sub-agent; runtime is offline; allowed submission extensions are restricted; unpacked size is below 3 GiB; all patches share a 12-hour total inference allowance.

**[VERIFIED: SRC-02]** The harness supports multiple discovered adapters and configures vLLM with `max_loras` equal to the discovered adapter count and detected maximum rank, bounded by its competition configuration. Each agent can declare one adapter string.

**[VERIFIED: SRC-03]** The resolver maps an adapter declaration to `openai/<adapter_name>` or the matching provider prefix. The adapter alias is therefore a request-routing model identity, not a second competition base model.

## Consequence

**[INFERRED: SRC-01–SRC-03]** A physically shared bank with arbitrary per-request rank masks is not exposed by the current declarative schema. The compatible construction is to learn one conceptual bank, compile each static gate or mixture into a standard adapter directory, and route concurrent requests by adapter alias.

# Architecture

## Frozen base and target modules

Let \(W_{0,l}\in\mathbb{R}^{d_{out,l}\times d_{in,l}}\) be target projection \(l\) in the frozen E4B text model. The exact module names and supported PEFT mapping must be enumerated from the CUDA training checkpoint before training; this design does not assume that every conventional projection name is accepted by the Gemma 4 implementation.

**[VERIFIED: SRC-12]** The inspected local configuration reports a 42-layer E4B text model with sliding and full-attention layers, hidden size 2,560, and 4-bit affine quantization metadata. This describes the local converted checkpoint and does not independently prove CUDA trainer compatibility.

**[PROPOSED]** Prefer training against the exact competition checkpoint through a verified differentiable dequantization/QLoRA path. If training uses a bfloat16 parent or any reconstructed surrogate, record lineage and hashes, then require adapter transfer tests on the exact deployed QAT base. A surrogate-trained win is not attributed to the competition base until that transfer gate passes.

## Shared rank-atom bank

For target module \(l\), define \(K_l\) ordered rank atoms:

$$
\mathcal{B}_l=\{(b_{l,k},a_{l,k})\}_{k=1}^{K_l},\qquad
b_{l,k}\in\mathbb{R}^{d_{out,l}},\quad
a_{l,k}\in\mathbb{R}^{d_{in,l}}.
$$

Role \(r\) has a sparse gate \(g_{r,l}\in\mathbb{R}^{K_l}\). Its effective update is:

$$
\Delta W_{r,l}=\sum_{k=1}^{K_l}g_{r,l,k}\,b_{l,k}a_{l,k}^{\top}.
$$

The role-specific forward projection is:

$$
h_l' = (W_{0,l}+\Delta W_{r,l})h_l.
$$

**[PROPOSED]** Partition the gate support into shared, role-private, and optionally pair-shared atoms. Shared atoms are candidates for reusable repository/tool behavior; private atoms are candidates for role-specific behavior; pair-shared atoms are admitted only when measured transfer exceeds interference. Semantic interpretations require the causal tests below.

## Roles

Initial agent roles are downstream routing choices. They are not presumed to be the model's internal ontology. Map the operations above first, then measure which combinations a role actually uses:

| Role | Training behavior | Primary output |
|---|---|---|
| `localization` | Resolve issue text to files and symbols using graph/source tools. | Evidence-ranked targets |
| `snapshot_coherence` | Check exact source relationships and reject stale/unsupported outlines. | Supported/contradicted claims |
| `structural_ir` | Convert exact source into bounded control/data representations. | Source-anchored IR |
| `api_risk` | Preserve captured signatures, exceptions, and public behavior; propose unknown hidden-test risks. | Constraints and adversarial risks |
| `implementation` | Produce minimal source edits and targeted checks. | Working-tree delta |
| `verification` | Inspect diff and run targeted adverse tests. | Judge receipts |

**[PROPOSED]** Begin with four adapter views—localization, analysis, implementation, verification—only after frozen-base probes. The twelve-view organization remains a testable later arm. Extra roles are admitted when operation-level interventions and trajectory evidence show useful separation, not because a role name appears in a prompt.

## Static mixtures

**[PROPOSED]** A role may use a mixture gate, for example:

$$
g_{implementation+api}=g_{implementation}+\beta g_{api},
$$

where \(\beta\) is selected on a development split. Each selected mixture is compiled before packaging and receives its own adapter alias. The scored runtime never optimizes \(\beta\).

# Exact Compilation into Standard LoRA

For active set \(S=\{k:g_k\neq0\}\), construct:

$$
B'=[\sqrt{|g_k|}b_k]_{k\in S},
$$

$$
A'=\begin{bmatrix}
\operatorname{sign}(g_k)\sqrt{|g_k|}a_k^\top
\end{bmatrix}_{k\in S}.
$$

Then:

$$
B'A'=\sum_{k\in S}g_kb_ka_k^\top=\Delta W(g).
$$

**[PROPOSED]** PEFT applies a runtime scale to the factor product, commonly \(s=\alpha/r\), and rank-stabilized LoRA changes that rule. The canonical export profile therefore sets `use_rslora: false` and \(\alpha=r=R\), making \(s=1\). Modules with fewer than \(R\) active atoms are zero-padded to rank \(R\). Any later profile with \(s\ne1\) must compile \(B'A'=\Delta W/s\) and prove equality after the actual loader applies its scale.

**[PROPOSED]** The compiler must verify both raw factor equality and loader-observed effective-delta equality numerically in FP32 before casting/export. It emits `adapter_config.json`, `adapter_model.safetensors`, a bank version, gate digest, source checkpoint digest, target-module list, scaling convention, padding map, and compilation receipt. A tensor-name, transpose, fan-in/fan-out, or alpha mismatch is a hard failure.

**[PROPOSED]** Do not post-compress with singular value decomposition unless the approximation error and task retention are measured. Truncation can erase the component identity the design intends to study.

# Factor Identifiability and Canonicalization

For any invertible matrix \(R\), LoRA factors satisfy:

$$
BA=(BR)(R^{-1}A).
$$

**[VERIFIED MATHEMATICAL FACT]** Raw factor coordinates are therefore not identifiable. Comparing \(A_i\) with \(A_j\), or \(B_i\) with \(B_j\), can report different overlap for identical effective deltas.

**[PROPOSED]** All cross-adapter analysis must use one of:

1. Effective update matrices \(\Delta W\).
2. Orthonormal bases obtained from the singular value decomposition of \(\Delta W\).
3. Canonical balanced factors with deterministic sign and singular-value ordering.
4. The shared bank's fixed atom index, when the bank basis is frozen and versioned.

## Gate-scale identifiability

**[VERIFIED MATHEMATICAL FACT]** Gate sparsity is ill-posed if atom magnitude is unconstrained: scaling an atom up while scaling its gate down preserves the effective delta but reduces an \(L_1\) gate penalty. Factor balancing alone does not remove this bank–gate ambiguity.

**[PROPOSED]** Canonicalize every atom so \(\lVert b_{l,k}\rVert_2=\lVert a_{l,k}\rVert_2=1\), absorb its signed magnitude into \(g_{r,l,k}\), and apply a deterministic sign convention. Enforce this through a constrained parameterization or a post-step projection that also transforms optimizer state. Sparsity, utilization, and overlap are reported only after canonicalization.

**[PROPOSED]** Track dead atoms, always-on atoms, pairwise atom coherence, gate entropy, and effective rank. Bank collapse—many duplicate atoms or all roles selecting the same support—is a failed specialization result even if the end-to-end score improves.

# Base Specialization Analysis

## Dataset construction

**[VERIFIED: SRC-20]** The local public dataset has 67 FastAPI, 48 Rich, 13 Requests, and one HTTPX task. It has no role-label field. A three-way repository-disjoint split gives very little data for tuning several ranks, penalties, and view counts.

**[PROPOSED]** Derive operation and role datasets from public training trajectories only. Freeze a small, named development fold before building labels, and reserve at least one complete repository for a single confirmatory look. Keep related issues, commits, and near-duplicate patches in one partition. Report the repository shift explicitly; never present a public-repository result as an estimate of the private competition score. A task, patch, test patch, or derivative trajectory cannot cross the declared boundary.

**[PROPOSED]** Every example records role, task id, repository, base commit, prompt, tool sequence, expected structured output, validity, and whether the final patch passed available tests. Failed trajectories remain available as negative examples but must be labeled.

## Frozen-base probes

For role dataset \(D_r\) and module \(l\), collect:

- Mean and covariance of module inputs and outputs.
- Gradient sketches of the role loss with respect to candidate projection weights.
- Diagonal or low-rank Fisher approximations when affordable.
- Tool-call validity and structured-output failure labels.
- Optional causal ablations of layer/projection groups.

**[INFERRED]** Agreement among gradients, activation shifts, and causal ablations is stronger evidence of functional specialization than any single signal. This inference ends before establishing that these signals identify stable Gemma 4 circuits.

## Sensitivity score

One pre-registered module score is:

$$
s_{r,l}=\eta_g\frac{\|G_{r,l}\|_F}{\sum_j\|G_{r,j}\|_F}
+\eta_a\frac{\operatorname{tr}(C_{r,l})}{\sum_j\operatorname{tr}(C_{r,j})}
+\eta_c\widehat{\Delta\mathcal{L}}_{r,l},
$$

where \(G\) is a gradient sketch, \(C\) an activation covariance statistic, and \(\widehat{\Delta\mathcal{L}}\) the normalized causal-ablation loss increase. Coefficients \(\eta\) are chosen on development data and frozen before held-out evaluation.

# Bank Initialization

Evaluate at least three initializers:

1. **Gradient SVD:** singular directions of concatenated role gradient sketches.
2. **Base SVD:** frozen projection singular vectors with trainable core coefficients, related to the LoRA-XS construction.
3. **Independent LoRA union:** canonicalize independently trained deltas, concatenate their leading atoms, then retrain gates.

**[PROPOSED]** Match total bank rank and trainable parameter count across initializers. A better result from a larger bank is not evidence for better allocation.

# Joint Training Objective

For role \(r\), let \(\mathcal{L}_{task}^{(r)}\) be supervised trajectory loss. The first bank experiment uses only task loss and canonicalized atom sparsity:

$$
\mathcal{L}=\sum_r w_r\mathcal{L}_{task}^{(r)}
+\lambda_{sparse}\sum_{r,l}\|g_{r,l}\|_1.
$$

The following are candidate ablations, not default penalties:

$$
\mathcal{R}_{overlap}=\sum_{r<s,l}\frac{\|g_{r,l}\odot g_{s,l}\|_1}{\|g_{r,l}\|_1+\|g_{s,l}\|_1+\epsilon},
$$

$$
\mathcal{R}_{gradient}=\sum_{r<s}\max(0,-\cos(\nabla\mathcal{L}_r,\nabla\mathcal{L}_s)),
$$

$$
\mathcal{R}_{retention}=\sum_r\mathbb{E}_{x\sim D_r^{retain}}
\left[\operatorname{KL}(p_{reference}(\cdot|x)\|p_r(\cdot|x))\right].
$$

**[PROPOSED]** Overlap is not always harmful. The overlap penalty must be ablated against learned overlap, hard disjointness, and random masks. Shared atoms should survive when they improve transfer without degrading role retention.

**[VERIFIED MATHEMATICAL FACT]** Even with unit-norm atoms, two near-collinear atoms can carry separate private gates while producing nearly identical effective deltas. The gate-overlap penalty and gate Jaccard can report separation that does not exist in weight space. Therefore neither is an interference measure or a primary proof of subnetwork separation. Freeze atom indices, measure atom coherence, and compare effective deltas and functional retention.

**[PROPOSED]** If used, apply gradient-conflict pressure only to predeclared shared atoms and compare it with no conflict penalty. Define \(p_{reference}\) before any retention ablation: for example, the frozen E4B distribution on a separate tool-format retention set. That KL then measures format retention on that set, not general reasoning retention. Do not select penalties from held-out outcomes.

# Gate Learning

Evaluate two gate families:

1. **Static top-k:** learn continuous scores, select the top-k atoms per module, retrain coefficients with the mask frozen.
2. **Structured group sparsity:** select complete rank atoms or module-level groups rather than unstructured individual weights.

**[PROPOSED]** Prefer structured atom sparsity because unstructured zeros do not automatically reduce serving cost. The canonical zero-padded export keeps dense rank \(R\), so it provides no rank-based storage or serving saving. A lower-rank export or PEFT per-module `rank_pattern` must pass the actual discovery and vLLM loader tests before any byte or speed advantage is claimed; the local rank detector reads top-level `r` and the server rounds its maximum rank to supported buckets.

**[PROPOSED]** The final gate is frozen before held-out evaluation. No hidden-task examples, test outcomes, or online router optimization may influence it.

# Overlap and Interference Measurements

For every pair of roles and target module, compute:

## Effective-delta cosine

$$
c_{rs,l}=\frac{\langle\Delta W_{r,l},\Delta W_{s,l}\rangle_F}
{\|\Delta W_{r,l}\|_F\|\Delta W_{s,l}\|_F+\epsilon}.
$$

## Principal-angle overlap

If \(Q_r,Q_s\) are orthonormal bases for selected update subspaces:

$$
o_{rs,l}=\frac{\|Q_r^\top Q_s\|_F^2}{\min(\operatorname{rank}Q_r,\operatorname{rank}Q_s)}.
$$

## Gate overlap

For binary supports \(S_r,S_s\):

$$
J_{rs,l}=\frac{|S_r\cap S_s|}{|S_r\cup S_s|}.
$$

## Sign conflict

Measure the fraction and magnitude of effective-delta coordinates whose signs disagree after excluding values below a pre-registered magnitude threshold.

## Functional interference

For adapter or mixture \(m\), define role retention:

$$
R_{r\leftarrow m}=\operatorname{score}(m,D_r)-\operatorname{score}(r,D_r).
$$

The full pairwise matrix is required. Average score alone can hide catastrophic loss of one role.

## Causal activation overlap

**[PROPOSED]** Compare per-layer activation changes against the frozen base and intervene on selected atoms or modules. Call the result “latent subnetwork evidence” only when removing the selected components selectively harms their assigned role more than controls.

# Runtime and Packaging

Directory example:

```text
adapters/
├── bank-localization/
│   ├── adapter_config.json
│   └── adapter_model.safetensors
├── bank-analysis/
│   ├── adapter_config.json
│   └── adapter_model.safetensors
├── bank-implementation/
│   ├── adapter_config.json
│   └── adapter_model.safetensors
└── bank-verification/
    ├── adapter_config.json
    └── adapter_model.safetensors
```

Agent example:

```yaml
# sub_agents/implementation.yaml — compiled static bank view
name: implementation_agent
model: gemma-4-e4b-it-qat-w4a16-ct
adapter: bank-implementation
instruction: !include ../prompts/implementation.md
tools:
  - read_file
  - edit_file
  - run_command
  - get_status
generate_content_config: !include ../configs/sampling.yaml
```

**[VERIFIED: SRC-02, SRC-03]** The base `model` string remains identical. `adapter` selects the compiled view, and the resolver maps that adapter to a served alias.

**[PROPOSED]** Store a manifest beside training outputs, not necessarily inside the scored adapter directory, containing bank version, gate vector, source checkpoint digest, module map, rank, alpha, training run, split digest, and compiler receipt.

# Concurrency Model

**[VERIFIED: SRC-02]** The documented harness setup discovers and registers multiple LoRA adapters against one base server.

**[PROPOSED]** Submit concurrent requests to distinct aliases so specialists can share that server instead of loading one full E4B instance per role. Treat actual concurrent scheduling, memory sharing, and isolation as unverified until the pressure test passes.

**[INFERRED]** Concurrent adapters still compete for scheduler capacity and key-value cache. This architecture does not imply free parallelism; concurrency must be pressure-tested at the actual context length and reasoning budget.

# Experimental Design

## Arms

| Arm | Description | Purpose |
|---|---|---|
| A0 | Frozen E4B, prompt-only roles | Base control |
| A1 | Independently trained LoRAs | Standard specialist control |
| A2 | Shared bank, dense gates | Tests shared basis without sparsity |
| A3 | Shared bank, hard-disjoint sparse gates | Tests maximal separation |
| A4 | Shared bank, learned-overlap sparse gates | Primary proposed method |
| A5 | Shared bank, random masks matched for rank/sparsity | Tests whether allocation matters |
| A6 | Always-on fused adapter | Tests loss of role routing |
| A7 | Precompiled role mixtures | Tests controlled composition |

**[PROPOSED]** These are a staged research menu, not a single immediate eight-arm campaign. Freeze the operation probes first. Phase 0 qualifies training and serving; A0/A1 establish a matched operational control; a small bank pilot tests whether steering the discovered pathway is feasible; only then pre-register the A2–A7 matrix. Do not infer that a one-seed A1 miss logically falsifies the bank; treat it as a noisy resource-allocation signal.

## Split protocol

1. Group tasks by repository.
2. Assign repositories, not individual tasks, to train/development/held-out partitions.
3. Freeze split manifest and SHA-256 digest before training.
4. Generate trajectories only from the assigned partition.
5. Use development data for rank, regularization, and gate selection.
6. Run held-out evaluation once per frozen candidate, subject to compute constraints.

## Budget matching

**[PROPOSED]** Report two fairness regimes because they answer different questions:

1. **Serving-matched:** equal active rank, target modules, prompt/agent graph, inference tokens, and time per request. This tests quality at equal runtime capacity.
2. **Family-matched:** equal total trainable parameters, examples, optimizer updates, and aggregate artifact bytes across the full adapter family. This tests whether sharing buys system-level efficiency.

Do not claim general superiority unless A4 passes the named regime; a win under one regime does not imply a win under the other. Within each regime, match or report:

- Number of training examples and tokens.
- Optimizer steps and effective batch size.
- Trainable parameters.
- Target modules and maximum exported rank.
- GPU type and wall time.
- Inference sampling parameters.
- Agent tool/time budgets.
- Agent hierarchy, prompts, tool permissions, and stopping policy.
- Bank and gate parameters separately from active exported parameters.

## Primary endpoint

**[PROPOSED]** Primary deployment endpoint: paired held-out resolved-task count under the official verification lifecycle and equal agent budgets.

## Secondary endpoints

- Valid nonempty patch rate.
- Tool-call validity.
- Target-file and target-symbol accuracy where labels exist.
- Per-role structured-output accuracy.
- Mean and tail task duration.
- Token consumption and tool calls.
- Adapter bytes and active rank.
- Pairwise merge/mixture retention matrix.
- Weight, subspace, gate, gradient, and activation overlap.

## Statistical reporting

**[PROPOSED]** Report paired task outcomes, resolved-count difference, exact McNemar test where applicable, and repository-stratified bootstrap confidence intervals. With few repositories, emphasize effect sizes and uncertainty rather than asymptotic significance.

**[PROPOSED]** Use at least three independent training seeds for every learned arm in the confirmatory research comparison. A one-seed result is preliminary and cannot support definitive stability, mechanistic, or superiority claims in the short paper.

**[PROPOSED]** Mark secondary analyses as confirmatory or exploratory before execution and correct families of confirmatory hypothesis tests for multiplicity. Exploratory plots may motivate later work but cannot be rewritten as pre-registered evidence.

# Quality Gates

1. **Q0 — Checkpoint identity:** exact E4B base and tokenizer hashes recorded.
2. **Q1 — Data integrity:** repository-disjoint split and no hidden/test-patch leakage.
3. **Q2 — Bank integrity:** fixed atom ordering, canonicalization, and manifest digest.
4. **Q3 — Compilation parity:** FP32 bank view equals exported LoRA delta within a pre-registered tolerance.
5. **Q4 — Adapter validity:** every exported directory passes submission validation and loads on the target server.
6. **Q5 — Independent utility:** each specialist exceeds or matches A0 on its role development metric.
7. **Q6 — Composition:** A4 outperforms A5 on pre-registered retention metrics; otherwise allocation is unsupported.
8. **Q7 — End-to-end:** candidate passes held-out patch verification and runtime limits.
9. **Q8 — Package:** total size, extensions, symlinks, rank, and single-base-model checks pass.
10. **Q9 — Honest release:** paper and README distinguish measured, inferred, and proposed claims.
11. **Q10 — Paper evidence:** every manuscript number and figure is regenerated from immutable run data; cross-checks pass before submission.

# Pressure Tests

| Failure | Assault | Required response |
|---|---|---|
| Factor gauge artifact | Apply random invertible transformations preserving \(BA\) | Overlap metrics must remain unchanged |
| Gate-scale artifact | Rescale atoms and compensate gates before canonicalization | Canonical gates and sparsity metrics must remain unchanged |
| Export scaling | Vary rank padding and alpha under equivalent deltas | Loader-observed outputs and deltas remain within tolerance |
| Bank collapse | Inspect atom utilization and singular spectrum | Reject if most roles select the same atoms without benefit |
| Artificial disjointness | Compare to random matched masks | No specialization claim unless learned allocation wins |
| Role starvation | Per-role retention matrix | Reject aggregate win hiding one catastrophic role |
| Stale checkpoint | Alter or mismatch base digest | Compiler/load must fail closed |
| Surrogate-base transfer | Train on any non-identical parent and evaluate on exact QAT base | No competition-base claim without preserved utility and recorded lineage |
| Rank overflow | Export above server maximum | Validator must reject |
| Package overflow | Sum all compiled views | Reduce rank/adapter count; never silently omit |
| Concurrent saturation | Parallel long-context requests | Record throughput, latency, failures, and memory pressure |
| Prefix/KV isolation | Interleave identical prefixes across adapter aliases and cache states | Each result matches its uncached single-alias control |
| Malformed tools | Role-specific tool-call suite | Reject adapter with increased malformed-call rate |
| Sparse-but-dense cost | Measure bytes and inference | Do not claim efficiency from zero weights alone |
| Overfit by repository | Hold out complete repositories | Reject generalization claim on within-repo split only |
| Merge sign conflict | Pairwise and full mixtures | Record sign/magnitude conflict and role retention |
| Orchestration confound | Hold prompts, hierarchy, tools, and stop policy fixed across adapter arms | Only adapter treatment differs |
| Mechanistic null | Use norm-matched random atoms and activation interventions | Claimed role selectivity exceeds controls |

# Failure and Stop Conditions

- Stop if the CUDA E4B checkpoint cannot be trained with the selected PEFT stack.
- Stop if exported adapters do not load through the competition vLLM path.
- Stop if compilation parity fails after one materially different correction.
- Stop deployment if held-out resolved count does not exceed the current candidate.
- Stop “latent subnetwork” language if causal ablations do not show role-selective effects.
- Stop mergeability claims if A4 does not beat random matched masks or independent LoRAs.
- Preserve negative results; do not retune the metric after reading held-out outcomes.

# Security, Compliance, and Data Governance

**[VERIFIED: SRC-01]** Training must use the permitted E4B base, remain reproducible, avoid credential disclosure, and respect competition data-sharing rules.

**[PROPOSED]** Training manifests store hashes and identifiers, not credentials. Adapter artifacts contain only safetensors and PEFT JSON. No pickle weights, external symlinks, absolute references, or runtime network dependencies are admitted.

**[PROPOSED]** Every training example and teacher trajectory records source dataset, repository, revision, license, generation model, prompt version, and split membership. Apache-2.0 release readiness for code and model artifacts does not erase upstream dataset or repository obligations. Unknown or incompatible provenance is an admission failure.

# Alternatives Considered

| Alternative | Advantage | Limitation | Decision |
|---|---|---|---|
| Independent LoRA per agent | Simple and directly supported | No coordinated basis or interference control | Required baseline |
| One merged always-on LoRA | One artifact and no routing | Loses specialist identity; interference possible | Experimental control |
| Runtime token-level router | Most expressive | Unsupported by competition schema/server path | Reject for submission |
| Prompt-only specialists | Zero training/package cost | May not recover small-model role failures | Required baseline |
| Full fine-tuning | Maximum flexibility | Not PEFT, expensive, incompatible with adapter study | Reject |
| Unstructured sparse deltas | Fine-grained masks | Standard serving may remain dense | Research-only control |
| Shared-base SVD core | Very small role coefficients | May constrain useful directions | Include initializer |

# Consequences

## Positive

**[INFERRED]** Coordinated gates could reduce duplicated updates, expose interpretable overlap matrices, and permit controlled static mixtures. Evidence ends before demonstrated Gemma 4 performance.

## Negative

**[VERIFIED/INFERRED]** Packaging requires separate compiled views because runtime rank gates are unavailable. Shared components may be duplicated across safetensors, and multiple adapters can increase serving overhead and submission size.

## Neutral

**[VERIFIED]** The competition still sees one base model. Adapter aliases change request routing, not base-model identity.

# Implementation Plan

## Phase 0 — Feasibility probe

1. Qualify activation capture on the frozen E4B checkpoint, including model/tokenizer identity and forward-output parity if a converted research copy is used.
2. Run the matched operation probes and intervention controls above. Record both positive and negative findings before adapter target selection.
3. Verify the exact CUDA checkpoint, PEFT target module names, and quantization-training path.
4. Train one rank-4 E4B adapter on a tiny non-held-out sample; export, validate, load, and run one tool-call smoke.
5. Record memory, time, artifact size, scale, declared and observed rank, and loader parity.

## Phase 1 — Data and independent controls

1. Freeze repository split, operation-label construction, role mapping, and lexical counterfactuals.
2. Generate verified positive and labeled negative trajectories without held-out gold or test patches.
3. Train A1 adapters with matched prompts, hierarchy, tools, stop policy, and budgets.
4. Establish end-to-end resolved-task outcomes, operation metrics, and failure taxonomy. Keep one-seed results exploratory.

## Phase 2 — Bank discovery

1. Use the frozen-base intervention results to nominate target module families; test whether they differ from equal-rank random and gradient-only choices.
2. Build initial bank variants with one atom index per target module.
3. Train dense gates, sparse gates, and random controls only under a frozen comparison manifest.
4. Canonicalize, check collinear splitting, and compute activation, delta, and functional retention matrices.

## Phase 3 — Compilation and serving

1. Compile role and mixture views.
2. Verify effective-delta parity.
3. Package standard adapters.
4. Run sequential and concurrent server qualification.

## Phase 4 — Held-out evaluation

1. Freeze candidates and hypotheses.
2. Run paired held-out evaluations.
3. Report all arms, failures, seeds, and uncertainty.
4. Admit, reject, or retain as paper-only result.

# Testing Evidence

## Current evidence

**[VERIFIED]** No adapter training, compiler, or coordinated-bank evaluation has been executed for this design. The MLX research-copy capture `observer/out/e4b-mlx-capture-20261111T074425Z` recorded repeated residual-ablation logit KL and admitted neither `critical` nor `unnecessary`. That run is not a basin, a pathway, or a competition-base LoRA result.

## Required test suites

| Test | Type | Required proof |
|---|---|---|
| Factor gauge invariance | Mathematical/property | Metrics unchanged under equivalent factor transforms |
| Compiler equality | Numerical/property | Bank-gated delta equals compiled LoRA delta |
| Safetensors round-trip | Integration | Save/load preserves tensors and manifest |
| Submission validation | Integration | Every candidate directory passes official validator |
| Single-model discovery | Compliance | Exactly E4B is discovered across hierarchy |
| Adapter routing | Integration | Correct alias produces correct compiled view |
| Concurrent serving | Pressure | Multiple aliases complete without corruption |
| Role utility | Evaluation | Specialists meet frozen role gates |
| Pairwise composition | Evaluation | Complete retention/interference matrix |
| End-to-end patches | Evaluation | Official verification lifecycle produces resolved counts |

## Reproduction command

**[PROPOSED]** The eventual implementation must provide one offline command that builds manifests, compiles views, validates packages, and runs property tests. No command exists yet; inventing one here would be misleading.

## Was it proven necessary?

**[VERIFIED]** No. Independent LoRAs have not yet been trained or shown inadequate. The architecture is justified as a research hypothesis about modularity and interference, not as an established corrective action.

# Deployment and Rollback

| Aspect | Design |
|---|---|
| Deployment | Candidate submission directory separate from `v0_baseline` |
| Rollout | Local smoke → held-out subset → full public evaluation → optional Kaggle candidate |
| Rollback | Select baseline submission or remove adapter declarations/directories |
| Runtime fallback | Route failed specialist to the base/prompt-only agent when pre-registered |
| Artifact restore | Rebuild from checkpoint digest, bank manifest, gate files, and compiler receipt |
| Monitoring | Resolution, malformed patches, tool validity, time, tokens, adapter load failures |

# Paper Evidence Package

**[PROPOSED]** The short paper is downstream of definitive experiments, not a substitute for them. No result section is finalized until the following evidence package exists:

1. Immutable run manifests with checkpoint, data-split, code, prompt, adapter, environment, and sampling digests.
2. Per-task machine-readable outcomes, verification receipts, timing, token/tool counts, failure categories, and seed identifiers.
3. Aggregate tables generated from those per-task records, including denominators and missing-run accounting.
4. Statistical comparison outputs with paired outcomes, effect sizes, confidence intervals, and the pre-registered test.
5. Deterministic figure scripts and source-data digests; no values copied manually into plotting code.
6. A claim ledger mapping each abstract/result claim to run IDs, table cells, figures, and analysis code.

Minimum planned figures are: held-out resolved-task comparison with uncertainty; paired win/loss matrix; quality–active-rank and quality–artifact-size Pareto curves; role-by-role retention/interference matrix; gate/subspace overlap heatmaps; causal intervention versus matched controls; and sequential/concurrent throughput with memory pressure. Failed runs and excluded tasks remain visible with pre-declared reasons.

**[PROPOSED]** A clean environment must regenerate all paper tables and figures from the frozen evidence package. The generated values are then checked against the manuscript. Any mismatch, undocumented exclusion, changed denominator, or post-hoc primary metric blocks paper submission.

# Next Stage of Implementation

| Next step | Description | Depends on this? | Target |
|---|---|---|---|
| External design review | Attack feasibility, novelty, metrics, and leakage risks | Yes | Before code |
| E4B PEFT feasibility probe | Rank-4 training/export/load smoke | Yes | After review |
| Machine schemas | Bank, gate, compiler receipt, experiment manifest | Yes | With probe |
| Independent LoRA baseline | Establish empirical need | Yes | Before coordinated bank |
| Coordinated-bank study | A2–A7 ablations | Yes | After controls |

**[PROPOSED]** This design sets up the next goal by defining a falsifiable architecture, exact runtime boundary, controls, and stop conditions. It does not set up deployment until the feasibility probe and independent-LoRA baseline pass.

# Review Questions for the Next Agent Set

1. Is the bank mathematically identifiable enough for the proposed overlap claims?
2. Should atoms be shared across layers, only within modules, or only within module families?
3. Can the target PEFT/vLLM versions load compiled E4B views without unsupported metadata?
4. Is joint bank training feasible on L4x4 with the quantized base, or must training use a dequantized/bfloat16 base and export to the QAT checkpoint?
5. Which role datasets can be constructed without leaking held-out repository structure?
6. Does role specialization improve end-to-end patches, or merely structured intermediate outputs?
7. Which overlap metric best predicts negative transfer after controlling for update norm?
8. Does sparsity improve composition beyond random matched masks?
9. How many compiled views fit under 3 GiB at useful rank?
10. Can concurrent multi-LoRA serving meet the 12-hour campaign budget?
11. What claims remain novel after comparison with PETA, LoRAHub, LoRA-XS, TIES, DARE, CtM, TaDA, and READ?
12. What result would falsify “latent subnetwork activation” rather than merely weaken it?

# Literature Grounding

| ID | Work | Version/year | License status | Design use |
|---|---|---:|---|---|
| SRC-04 | Hu et al., “LoRA: Low-Rank Adaptation of Large Language Models” | arXiv:2106.09685, 2021 | arXiv-hosted; paper-specific license not independently verified | Low-rank frozen-base adaptation |
| SRC-05 | Ilharco et al., “Editing Models with Task Arithmetic” | arXiv:2212.04089, 2022 | arXiv-hosted; paper-specific license not independently verified | Weight-space task vectors |
| SRC-06 | Yadav et al., “TIES-Merging” | arXiv:2306.01708, 2023 | arXiv-hosted; paper-specific license not independently verified | Redundancy/sign interference |
| SRC-07 | Yu et al., “Language Models are Super Mario” | arXiv:2311.03099, 2023 | arXiv-hosted; paper-specific license not independently verified | DARE sparsification and merging |
| SRC-08 | Huang et al., “LoraHub” | arXiv:2307.13269, 2023 | arXiv-hosted; paper-specific license not independently verified | Dynamic LoRA composition |
| SRC-09 | Tang et al., “Parameter Efficient Multi-task Model Fusion with Partial Linearization” | arXiv:2310.04742, 2023 | arXiv-hosted; paper-specific license not independently verified | Adapter-space task arithmetic |
| SRC-10 | Bałazy et al., “LoRA-XS” | arXiv:2405.17604, 2024 | arXiv-hosted; paper-specific license not independently verified | Shared frozen bases with small trainable cores |
| SRC-11 | Zhang et al., “Rethinking Inter-LoRA Orthogonality” | arXiv:2510.03262, 2025 | arXiv-hosted; paper-specific license not independently verified | Orthogonality is not sufficient for semantics |
| SRC-13 | He et al., “Compress then Merge” | arXiv:2606.03723, 2026 | arXiv-hosted; paper-specific license not independently verified | Shared low-rank core before merging |
| SRC-14 | To et al., “TaDA” | arXiv:2606.05016, 2026 | arXiv-hosted; paper-specific license not independently verified | Layer/component-aware gated merging |
| SRC-15 | Li et al., “New LoRA Skills Should Read but Never Write” | arXiv:2609.31600, 2026 | arXiv-hosted; paper-specific license not independently verified | Canonical factors and directional coupling |
| SRC-18 | Men et al., “ShortGPT: Layers in Large Language Models are More Redundant Than You Expect” | arXiv:2403.03853, 2024 | arXiv-hosted; paper-specific license not independently verified | Layer redundancy motivates intervention, without an E4B retention claim |
| SRC-19 | Ma et al., “Do Sparse Autoencoders Identify Reasoning Features in Language Models?” | arXiv:2601.05679, 2026 | arXiv-hosted; paper-specific license not independently verified | Lexical decoy and causal falsification controls |

Links:

- <https://arxiv.org/abs/2106.09685>
- <https://arxiv.org/abs/2212.04089>
- <https://arxiv.org/abs/2306.01708>
- <https://arxiv.org/abs/2311.03099>
- <https://arxiv.org/abs/2307.13269>
- <https://arxiv.org/abs/2310.04742>
- <https://arxiv.org/abs/2405.17604>
- <https://arxiv.org/abs/2510.03262>
- <https://arxiv.org/abs/2606.03723>
- <https://arxiv.org/abs/2606.05016>
- <https://arxiv.org/abs/2609.31600>
- <https://arxiv.org/abs/2403.03853>
- <https://arxiv.org/abs/2601.05679>

# Local Source Register

| ID | Path | Version/date | License | Claim |
|---|---|---|---|---|
| SRC-01 | `AGENTS.md` | workspace 2026-11-10 | Project-local; not stated | Project model/tool/package/time constraints |
| SRC-02 | `DataSets/public/HARNESS_README.md` | dataset copy read 2026-11-11 | Apache 2.0 dataset documentation | Multi-LoRA serving and competition runtime |
| SRC-03 | `.venv-harness/lib/python3.13/site-packages/swegemma/harness/agent_runner.py:64` | swegemma 0.2.11 | Installed package; not independently rechecked | Adapter alias resolver |
| SRC-12 | `/Users/stewartbarteau/models/gemma-4-e4b-it-qat-w4a16-mlx/config.json` | local conversion read 2026-11-11 | Model license not independently rechecked | Local E4B architecture metadata |
| SRC-16 | `../GitHub/MetaSuperIntelligenceLabs-GlobalHack-A-thon-SoloDevTrack/results/glimmer-forward/carved-swarm-demo-2026-11-04.txt` | local demo record 2026-11-04, read 2026-11-11 | Project-local; not stated | One frozen Glimmer weight set, scoped-view behavior and union control |
| SRC-17 | `../GitHub/MetaSuperIntelligenceLabs-GlobalHack-A-thon-SoloDevTrack/results/glimmer-forward/quality-with-without-atoms-2026-11-04.txt` | local test record 2026-11-04, read 2026-11-11 | Project-local; not stated | Six-fact matched/absent/mismatched recalled-atom comparison |
| SRC-20 | `DataSets/public/data/tasks.jsonl` | local public dataset read 2026-11-11 | Dataset terms governed by competition; not independently rechecked here | Four-repository counts and absence of role labels |
| SRC-21 | `../GitHub/MetaSuperIntelligenceLabs-GlobalHack-A-thon-SoloDevTrack/globalmind-runtime/CARVED-MCP-RECALL-DESIGN.md` | local design read 2026-11-11 | Project-local; not stated | Scoped recall and capability boundary |
| SRC-22 | `../GitHub/MetaSuperIntelligenceLabs-GlobalHack-A-thon-SoloDevTrack/globalmind-runtime/contracts/whitehead-gamma12-v1.contract` | local contract read 2026-11-11 | Project-local; not stated | Twelve-well H3×T2 geometry contract |
| SRC-23 | `/Users/stewartbarteau/Desktop/Atoma-Papers/4-Assembling-Brigade-Style-Agentics-2026-11-04.pdf` | local preprint read 2026-11-11 | Project-local; not stated | Brigade receipts and limits of seeded-swarm evidence |

# What We Learned

| Category | Learning |
|---|---|
| Technical | A bank can remain conceptually unified while competition deployment requires separately compiled adapter views. |
| Mathematical | Raw LoRA factors are gauge-dependent; effective deltas or canonical subspaces are required for valid overlap claims. |
| Experimental | Sparsity and orthogonality need random-mask and retention controls; neither implies semantic modularity. |
| Runtime | Adapter aliases are routing identities layered on one legal base model. |
| Process | The independent-LoRA baseline is necessary to prove the coordinated method solves a real problem. |
| Estimation | The unknown CUDA/PEFT compatibility is the first blocking uncertainty, not the merger algorithm. |
| Prior art | The carved Glimmer swarm proves same-weight scoped information can change behavior; E4B internal-pathway steering remains a separate empirical question. |

# Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| 0.3.0 | 2026-11-11 | Codex | Added carved-swarm evidence, operation-level basin probes, causal and lexical controls, staged bank admission, and corrected the provisional loss and rank-efficiency claims. |
| 0.2.0 | 2026-11-11 | Codex | Added separated hypotheses, scale-correct compilation, gate identifiability, dual fairness budgets, isolation controls, provenance, and a mandatory paper evidence package. |
| 0.1.0 | 2026-11-11 | Codex | Initial rigorous research architecture for external agent review. |
