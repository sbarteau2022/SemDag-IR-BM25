# Gemma 4 Developer Agent Competition: Audit (as of 2026-11-10)

Source: kaggle.com pages read in the in-session browser on 2026-11-10.

## Two competitions, one sponsor

| | Main competition (leaderboard) | Paper Track (writeup) |
|---|---|---|
| URL | kaggle.com/competitions/gemma-4-developer-agent | kaggle.com/competitions/gemma-4-developer-agent-paper |
| What you submit | An agent config (zip) that fixes real Python bugs | A Kaggle Writeup, max 3,000 words |
| Scoring | PASS/FAIL per issue, SWE-bench style, on a hidden test set | Five criteria, 0 to 5 each: Novelty, Quality, Relevance, Verifiability, Clarity |
| Prizes | $37k / $18k / $10k, plus $10k Small Model bonus | $15k Best Paper, $10k Best New Resource, $10k Best New Application |
| Entry | Join Competition (accept rules) | Separate sign-up; you can enter both |

## Timeline (all 11:59 PM UTC unless noted)

**Paper Track**
- Sept 22/23, 2026: start
- **Nov 12, 2026: final submission (2 days away)**

**Main competition**
- Sept 23, 2026: start
- Nov 12, 2026: research paper and Small Model bonus date (see open question below)
- **Nov 25, 2026: entry deadline and team merger deadline**
- **Dec 2, 2026: final submission deadline (22 days away)**

## What you can do

- Use Gemma 4 with LoRA (PEFT) adapters, prompts, sub-agents, and ADK skills.
- Pick any one of the four allowed models: `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`, `gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`.
- Add optional LoRA adapters as `.safetensors` folders under `adapters/<name>/`.
- Write your own Python or bash helper scripts (they run in the sandbox).
- Use the provided tools: `run_command`, `read_file`, `edit_file`, `write_file`, `submit_patch`, `get_status`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`.
- Use external data or tools if they are publicly available to everyone, or cost little and are reasonably accessible.
- Use automated ML tools if you hold a license for them.
- Train on the public dev data (129 tasks, plus the code graphs and embeddings).
- Team up to 5 people. Merge teams before Nov 25.
- Submit once per day. Pick 2 final submissions for judging.
- Use L4x4 accelerators (about 96 GB, per the page), but only in notebooks attached to this competition. They use GPU quota at 2x the normal rate.
- Enter the Paper Track and the main track at the same time.
- Publish your code on the forums or as a public notebook; that is encouraged.

## What you cannot do

- **Use any model not on the allowed list.** Claude, GPT, Gemini and others are out.
- **Mix models.** Every agent and subagent in a submission must use the same base model.
- **Use the internet at runtime.** The sandbox has no network. L4x4 notebooks have internet disabled.
- **Hand-label or hand-predict** the validation or test data.
- **Share code privately** outside your team during the competition.
- **Keep the winning solution closed.** Winners must license the code and model under an OSI open-source license (the page says Apache 2.0) and deliver training code, inference code, and reproduction steps.
- **Exceed 12 hours** for all patches, including sandbox setup.
- **Reach outside the submission folder.** No `../` paths, no symlinks that point outside.
- **Call tools outside the harness list.** Custom sub-agents are allowed, but only ones you define.
- **Submit more than once a day**, or use more than one Kaggle account.
- **Use data or tools that are not reasonably accessible** or that cost more than the prize.
- **Enter from a sanctioned region** (Crimea, DNR, LNR, Cuba, Iran, North Korea).
- **Win if you work for Google or Kaggle.** Employees may enter but cannot win prizes.
- **Submit a paper that has already been published.** The Paper Track needs original, unpublished work.
- **Go over 3,000 words** on the Paper Track.

## Data and harness

- Public dev set: 129 tasks (`tasks.jsonl`) across repos such as fastapi, rich, requests, and httpx.
- Each task has a git snapshot, a serialized code graph (NetworkX), precomputed 256-dim node embeddings, and a `test_patch` (hidden at grading).
- Wheels are pre-built offline (124 files). The container is Python 3.13.
- Total dataset size: about 22.4 GB, 524 files, Apache 2.0.
- Start with `HARNESS_README.md`, `sample_submission/`, and the `swegemma` and `adk-eval-core` tools.

## Participation (as of audit)

- 15,863 entrants, 5,982 participants, 5,328 teams, 41,065 submissions (main).
- Paper Track: 7,169 entrants, 911 submissions.

## Open questions to verify

1. **Small Model bonus deadline.** The page lists Nov 12 in one place and "same as main track" in another. Confirm in the rules before relying on either.
2. **Rules page.** The rules text loaded only after the browser showed a reCAPTCHA. I read the text as shown; I did not interact with the check. Accept the rules yourself on Kaggle.
3. **Winning-code license.** The page says Apache 2.0 in the rules block. Confirm that is the license you want to ship under.

## Actions only you can take

- Click **Join Competition** and accept the rules (explicit consent, so I did not do it).
- Download the 22.4 GB dataset if you want it local (I have not downloaded anything).
