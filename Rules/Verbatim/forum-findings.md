# Forum findings: official answers to open questions

Fetched 2026-11-13 (UTC). Sources: Kaggle internal API (`competitions.PageService/ListPages`, `discussions.DiscussionsService/GetTopicListByForumId` + `GetForumTopicById`). Both forums were downloaded in full: 420 topics and 1,464 messages (main forum 11630393, paper forum 12784402). Raw JSON is in `raw/forum/`, and every staff or host message is in `forum-staff-posts.md`.

Who counts as official here:
- **Ryan Holbrook**: Kaggle STAFF, `authorType: ADMIN`.
- **Dustin**: Kaggle STAFF, ADMIN.
- **Ashley Oldacre**: Kaggle STAFF, ADMIN.
- **Elan Markowitz**: `authorType: HOST` (Google Research / Gemma team).
- **Bryan Perozzi**: no posts in either forum.

Quotes are verbatim. Dates are post dates in UTC.

---

## Q1. Small Model ($10k E2B/E4B) bonus deadline: Nov 12 or Dec 2?

**Answer: Dec 2, 2026, 23:59 UTC (official, host).** The one sentence that conflicts is on the Prizes page, and it belongs to the paragraph about the paper track.

- **Elan Markowitz (HOST), 2026-10-20**, "🌟Bonus Prize: Small Model Development ($10,000)", https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751104#3541749
  > "**Deadline:** Same submission deadlines apply as the main track prizes."
  > "**Award:** $10,000 to the highest-ranking submission utilizing **Gemma E2B** or **Gemma E4B**. Final scores are based on the private test set performance. Same submission rules and tie-breaking apply."
- **Official Prizes page** (`prizes.md`) says the same thing: "- **Deadline:** Same submission deadlines apply as the main track prizes."
- **Official Timeline page** (`timeline.md`): "**November 12, 2026 (optional)** - Deadline to submit Research Paper." and "**December 2, 2026** - Final Submission Deadline."
- **Main competition API metadata** (`raw/main-GetCompetition.json`): `"deadline":"2026-12-02T23:59:00Z"`.
- **Where the confusion comes from:** the last paragraph of the Prizes page ends with "Submissions must be made by **November 12, 2026 at 11:59PM UTC**." That paragraph talks about paper-track work ("Top submissions will be highlighted at a Google hosted event…"). It was placed after the Small Model section, so it reads as if it covers that prize too. The paper track's own deadline is `2026-11-12T23:59` (`raw/paper-GetCompetition.json`).
- Participants asked staff to settle this on 2026-11-09, but **no staff reply had been posted as of the fetch date**: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/757244. The host statement and the Prizes page's own "Deadline" bullet both say Dec 2.

## Q3. Does the scorer run tasks concurrently? What happens past 12 hours?

**Concurrency: tasks run sequentially (official).** Parallel tool calls are not supported. A `ParallelAgent` can make concurrent LLM calls, but tool calls still run one at a time.

- **Ryan Holbrook (STAFF), 2026-09-24**, "Scoring-run questions: task concurrency, eval_config keys, and the 12 h limit", https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3527819 . He was asked "Are hidden tasks evaluated sequentially or with some concurrency?" and answered:
  > "1. Sequentially."
- **Ryan Holbrook (STAFF), 2026-09-28**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743964#3529469
  > "- Parallel: I we don't support parallel calls."
- **Ryan Holbrook (STAFF), 2026-10-11**, "New Gemma 4 Models Available", https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3536861
  > "You could also experiment with using `ParallelAgent` for concurrent LLM calls (though tool calls are still executed sequentially)."
- Scale of the run. **Ryan Holbrook (STAFF), 2026-09-29**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744258#3530082
  > "There are ~120 tasks in the test set, or about 60 in each of the public and private splits. They are scored during the same 12-hour run."
- What counts toward the 12 hours. **Ryan Holbrook (STAFF), 2026-10-07**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745805#3534268 , answering Q6 "Does the 12-hour limit include vLLM server start-up?":
  > "6. Yes."
- Patch validation time. **Ryan Holbrook (STAFF), 2026-09-26**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743663#3528731
  > "IIRC, patch validation takes around two hours if a patch is submitted for every task. If no patch is submitted for a task, then validation is skipped and that task just scores 0. A "no patch" submission only takes about ten minutes."

**Going over 12 hours: the whole submission errors (official, latest statement).** Staff said they planned a change to score unfinished tasks as 0, then withdrew that plan. No later staff post says the change shipped.

- **Ryan Holbrook (STAFF), 2026-09-24**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3527819
  > "3. Currently, hitting the 12-hour limit will error, but I'm planning on a fix that will score unfinished tasks as 0. You may want to set `max_time_minutes` to something moderate as a failsafe."
- **Ryan Holbrook (STAFF), 2026-09-28**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743964#3529469
  > "- 12h overrun: Not yet. Budget per task using `eval_config.yaml`."
- **Ryan Holbrook (STAFF), 2026-10-07**, same thread, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3534253
  > "I'm reconsidering this request. The trouble is that we run both the public and the private tasks during the same 12 hour evaluation, and it's not clear to me yet how to support assigning 0 to unfinished tasks in a way that's fair and consistent."
- **Ryan Holbrook (STAFF), 2026-10-15**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749597#3539198
  > "Naively setting unfinished tasks to 0 could lead to inconsistent results on the public and private leaderboards. I will try to think of other ways we could allow teams to better utilize the 12 hours, though."
- Participant reports (not official) of the error text: "Your submission notebook exceeded the allowed runtime" (Marco Pereira, 2026-10-12, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748618). That thread has no staff reply.
- On Stewart's idea of running graph compiling and baseline tests in parallel: the staff answers above only cover how the scorer runs tasks (one after another, with sequential tool calls). They do not rule out running commands in the background inside one task's sandbox, such as `&` inside `run_command`, but no staff post talks about that either. **No official answer found** on in-sandbox background processes.

## Q5. Can we fine-tune (SFT/LoRA/distillation) on trajectories from frontier or closed models?

**Answer: allowed, as long as the use follows that model's license and terms, and the output does not conflict with this competition's license rules (official, STAFF, 2026-09-29).** Open-model trajectories and public trajectory datasets are explicitly permitted (HOST, 2026-10-05).

- The original question (c-number, 2026-09-23) asked whether participants "may use proprietary models, such as OpenAI Astra or Claude Opus 5.5, to generate code patches and agent trajectories for training Gemma specifically for this competition". It also asked about teacher restrictions and winner licensing.
- **Ashley Oldacre (STAFF), 2026-09-29**, "Clarification on distillation from external LLMs", https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742807#3530102
  > "Hello and thank you for your question and your patience. As long as you are using those models in accordance with their model license terms, and the output you're using to submit to that competition doesn't 'conflict with the license requirement of the rules of this competition, you may use them."
  - A participant asked a follow-up 12 minutes later: "So models like Claude and GPT are off the table, but Muse and Chinese aren't?" **No staff reply.** Staff never said whether any particular provider's terms allow this. That remains the participant's responsibility.
- **Ryan Holbrook (STAFF), 2026-09-28**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743964#3529469
  > "- Training data: Training on gemma-4-31b itself is fine. We'll try to have an answer for outputs from other models soon."
- **Elan Markowitz (HOST), 2026-10-05**, "Allowed training data for LoRA adapters: trajectories from other open models?", https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746046#3533331 . He answered both cases: (1) trajectories from a different open-weight model, and (2) public SWE-bench-style trajectory datasets on Hugging Face produced by non-Gemma models.
  > "Both cases are permitted."
- Related, on the paper track. **Elan Markowitz (HOST), 2026-10-05**, https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/745712#3533328
  > "Using Codex and other resources is permitted but it is your responsibility to follow terms of service, and make sure you meet all the submission requirements of the competition."
- Related, on paper datasets that include traces. **Elan Markowitz (HOST), 2026-10-27**, https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3545672
  > "Yes, it can include such traces. Please cite and reference the upstream license for the data."

**Rules text, verbatim (`rules.md`, main competition):**

1. COMPETITION-SPECIFIC TERMS:
   > "<h4>6. WINNER LICENSE TYPE</h4> Open Source Apache 2.0
   > <h4>7. DATA ACCESS AND USE</h4> Competition Use and Commercial Apache 2.0"

2.5 WINNER LICENSE:
> "a. Under Section 2.8 (Winners Obligations) of the General Rules below, you hereby grant and will grant the Competition Sponsor the following license(s) with respect to your Submission if you are a Competition winner:
>
> 1. You hereby license and will license your winning Submission and the source code used to generate the Submission under an Open Source Initiative-approved license (see [www.opensource.org] (http://www.opensource.org)) that in no event limits commercial use of such code or model containing or depending on such code.
>
> 2. For generally commercially available software that you used to generate your Submission that is not owned by you, but that can be procured by the Competition Sponsor without undue expense, you do not need to grant the license in the preceding Section for that software.
>
> 3. In the event that input data or pretrained models with an incompatible license are used to generate your winning solution, you do not need to grant an open source license in the preceding Section for that data and/or model(s).
>
> b. You may be required by the Sponsor to provide a detailed description of how the winning Submission was generated, to the Competition Sponsor's specifications, as outlined in Section 2.8, Winner's Obligations. This may include a detailed description of methodology, where one must be able to reproduce the approach by reading the description, and includes a detailed explanation of the architecture, preprocessing, loss function, training details, hyper-parameters, etc. The description should also include a link to a code repository with complete and detailed instructions so that the results obtained can be reproduced."

2.6 EXTERNAL DATA AND TOOLS. The rules have no separate "AI models" section; LLMs are covered inside 2.6.b:
> "a. You may use data other than the Competition Data ("External Data") to develop and test your Submissions. However, you will ensure the External Data is either publicly available and equally accessible to use by all Participants of the Competition for purposes of the competition at no cost to the other Participants, or satisfies the Reasonableness criteria as outlined in Section 2.6.b below. The ability to use External Data under this Section does not limit your other obligations under these Competition Rules, including but not limited to Section 2.8 (Winners Obligations).
>
> b. The use of external data and models is acceptable unless specifically prohibited by the Host. Because of the potential costs or restrictions (e.g., "geo restrictions") associated with obtaining rights to use external data or certain software and associated tools, their use must be "reasonably accessible to all" and of "minimal cost". Also, regardless of the cost challenges as they might affect all Participants during the course of the competition, the costs of potentially procuring a license for software used to generate a Submission, must also be considered. The Host will employ an assessment of whether or not the following criteria can exclude the use of the particular LLM, data set(s), or tool(s):
>
> 1. Are Participants being excluded from a competition because of the "excessive" costs for access to certain LLMs, external data, or tools that might be used by other Participants. The Host will assess the excessive cost concern by applying a "Reasonableness" standard (the "Reasonableness Standard"). The Reasonableness Standard will be determined and applied by the Host in light of things like cost thresholds and accessibility.
>
> 2. By way of example only, a small subscription charge to use additional elements of a large language model such as Gemini Advanced are acceptable if meeting the Reasonableness Standard of Sec. 8.2. Purchasing a license to use a proprietary dataset that exceeds the cost of a prize in the competition would not be considered reasonable."

2.8 WINNER'S OBLIGATIONS, a.1 (excerpt):
> "For avoidance of doubt, delivered software code should include training code, inference code, and a description of the required computational environment."

General rules, warranty clause (`foundational-rules.md`):
> "a. You warrant that your Submission is your own original work and, as such, you are the sole and exclusive owner and rights holder of the Submission, and you have the right to make the Submission and grant all required licenses. You agree not to make any Submission that: (i) infringes any third party proprietary rights, …"

What this means in practice (my reading, not an official statement):
- The competition allows frontier-model data. The real limit is each provider's terms of service: whether its outputs may be used to train another model, and whether the resulting weights can then be released under Apache 2.0. Staff explicitly left that check to participants.
- A winner must release the adapter under an open license that "in no event limits commercial use". Section 2.5.a.3 waives this only for "input data or pretrained models with an incompatible license", not for the participant's own trained weights.

## Q7. Does the scorer cap eval_config.yaml values? Is there a maximum?

**Answer: no official cap.** Staff said the scorer reads only four fields, and "The default is no limit." Nobody has stated a maximum. In practice the 12-hour total is the binding limit, and verification uses a fixed 300-second pytest timeout that you cannot change.

- **Ryan Holbrook (STAFF), 2026-09-24**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3527819 . He was asked whether `timeout_seconds`, `max_tool_calls`, `max_time_minutes` and `max_turns` are all supported, and what defaults apply:
  > "2. The scorer reads those, and only those, four fields. The default is no limit."
- **Ryan Holbrook (STAFF), 2026-10-12**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748428#3537307
  > "1. A participant's `eval_config.yaml` doesn't affect scoring. The only thing the scorer gets are the submitted patches. The `pytest` run in the scorer gets a timeout of 300 seconds to prevent hung tests from killing the whole submission. The gold patches finish well within this time."
- **Ryan Holbrook (STAFF), 2026-10-12**, same thread, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748428#3537362
  > "Yes, the `eval_config.yaml` applies when the agent is running."
- Conflict with the harness docs (not official forum text): the local `DataSets/public/data/HARNESS_README.md` lists harness defaults when a field is omitted. They are `max_time_minutes` 60.0, `max_tool_calls` "`100` in `inference.py` / `None` in CLI", `max_turns` "`500` turns (`None` → `500`…)", and `command_timeout_seconds` 300. A single command's timeout is also `min(command_timeout_seconds [300s], max(5, int(remaining_time_seconds)))`. These defaults do not match "The default is no limit". Trust the code in the wheelhouse that the scorer actually uses, and test it locally.
- A follow-up asking whether the four fields are enforced as hard cuts (https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748618, 2026-10-12) has **no staff reply**.

## Q2. Are .sh files allowed in skill scripts?

**No official forum answer found.** No staff or host post mentions `.sh` files. The rule that is actually enforced, the published harness allowlist, excludes them:

- `DataSets/public/data/HARNESS_README.md`, `allowed_file_extensions`:
  > "Strictly required formats only: `.yaml`, `.yml` (agent/eval configs), `.md`, `.txt` (prompts & `SKILL.md`), `.py` (ADK skill scripts), `.json` (`adapter_config.json`), and `.safetensors` (`adapter_model.safetensors`). Pickle-based weights (`.bin`, `.pt`, `.pth`) and other binary/archive extensions are rejected."
- The official Evaluation page's example tree says the opposite: "`scripts/            # Python or bash scripts executed in a sandbox`" (`evaluation.md`).
- Staff did confirm the scorer rejects files outside the allowlist. **Ryan Holbrook (STAFF), 2026-10-14**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749200#3538603
  > "It looks like your submission is failing because the zip contains a Python bytecode cache file (`.pyc`), which are not files accepted by the scorer."
- On custom tools. **Ryan Holbrook (STAFF), 2026-09-26**, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743573#3528747
  > "Include them as scripts in a skill. They will be available in the sandbox and your agent can execute them there."
- Safe choice: ship scripts as `.py`. A `.py` script can call `subprocess`, and bash can sit in a `.txt` or `.md` resource and be run through `run_command "bash file"`. A `.sh` file risks failing the whole submission, the same way the `.pyc` file did.

---

## Summary

| Q | Official answer? | Answer |
|---|---|---|
| Q1 Small-model deadline | Yes (HOST, 2026-10-20, plus Prizes and Timeline pages) | Dec 2, 2026, 23:59 UTC. The "Nov 12" sentence belongs to the paper-track paragraph. A staff clarification request from 2026-11-09 is still unanswered. |
| Q3 Concurrency / 12 h overrun | Yes (STAFF) | Tasks run sequentially, and parallel tool calls are unsupported. Going over 12 h errors the whole submission; the "unfinished = 0" fix was planned and then withdrawn (latest 2026-10-15). vLLM start-up counts toward the 12 h. |
| Q5 Frontier-model trajectories | Yes (STAFF, 2026-09-29; HOST, 2026-10-05) | Allowed if used under the model's license or terms, and the output does not conflict with the competition's license rules. Open-model and public trajectory datasets are allowed. Checking provider terms is up to us. |
| Q7 eval_config caps | Partial (STAFF) | The scorer reads only the four fields, and "the default is no limit"; no maximum is stated. Verification pytest is fixed at 300 s. The harness README lists different defaults (60 min, 100 calls, 500 turns, 300 s). |
| Q2 `.sh` in skills | No official answer | The harness allowlist excludes `.sh`, and staff confirmed off-list files (`.pyc`) fail the submission. Use `.py`. |
