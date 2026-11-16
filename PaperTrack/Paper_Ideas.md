# Paper Track: ideas

Deadline: **Nov 12, 2026** (11:59 PM UTC). Max 3,000 words. Scored on Novelty, Quality, Relevance, Verifiability, Clarity (0 to 5 each).

## Ranked by fit for a two-day window

1. **Ablation: do code-graph tools help a 4B agent?**
   Compare E4B with (a) plain grep and file reads vs (b) graph tools (`get_code_neighbors`, `search_similar_code`). Report pass rate and token cost on the 129 public tasks.
   Fits: Verifiability, Clarity. Low build cost.

2. **Quantization and tool-call reliability.**
   Test whether the 4-bit QAT build loses tool-call accuracy on multi-turn tasks, and at what point it breaks.
   Fits: Novelty, Relevance. Honest and measurable.

3. **Best New Resource ($10k): failure-taxonomy dataset.**
   Release labeled agent trajectories from E4B runs with a failure taxonomy (wrong file, bad edit, tool misuse, timeout).
   Fits: Best New Resource category directly. Needs a clean data release.

4. **Best New Application ($10k): graph-guided localization for small models.**
   Use the code graph to narrow candidate files before the agent starts, then measure gains.
   Fits: the application category ("creative uses of code-graphs").

5. **Tasks & Benchmarks: perturbation robustness.**
   Create variants of public issues (renamed symbols, reworded problem statements) and measure how often the agent still passes.
   Fits: Tasks & Benchmarks topic. Good for Quality (generalization).

## Recommendation

Do **#1 plus #2 as one paper**: "Does a 4B quantized agent need code graphs, and where does it break?"
- One claim, two experiments, one table.
- Verifiability is strong because all numbers come from the same harness.
- Honest limits section costs little and scores on Clarity.

If the baseline is weak, switch to **#3**. A resource paper needs less novel modeling and still scores.

## Writeup outline (3,000 words max)

1. Title and subtitle
2. Abstract (150 words)
3. Introduction: the gap (large cloud agents vs small local ones)
4. Setup: model, harness, tools, dev split
5. Experiments: baseline, graph-tool ablation, quantization check
6. Results: one table, one figure at most
7. Limitations
8. Related work and citations
9. Reproduction: link to public notebook

## Reminders
- Must be unpublished original research.
- Keep the public notebook public (no login wall). Private notebooks go public after the deadline.
- Draft writeups do not count. Submit, don't just save.
