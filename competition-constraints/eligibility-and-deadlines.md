# Model, Eligibility, Deadlines and Prizes

Tags: see [README.md](README.md).

## 1. Base model (MUST)

- [HR §3.2] "**All agents in a submission must declare at most ONE unique base model** (`len(models) == 1`), and in Kaggle competition scoring (`scripts/inference.py`) that model must be in `ALLOWED_MODEL_NAMES` (`gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`, `gemma-4-e4b-it-qat-w4a16-ct`, or `gemma-4-e2b-it-qat-w4a16-ct`). Declaring multiple base models or an unpermitted model raises `ParticipantVisibleError`."
- The check covers the root config, every `sub_agents[*].config_path`, every `agent_tool.config_path`, and any standalone agent YAML in the directory. A stray unused YAML with a different model would still fail. Provider prefixes (`openai/`, `hosted_vllm/`, ...) are stripped before comparing.
- The bf16 aliases (`gemma-4-e4b-it`, etc.) are for **local CLI only**. [HR §3.1]
- **This project's choice:** `gemma-4-e4b-it-qat-w4a16-ct` (`Rules/Overview/Model_Choice.md`).

## 2. Small Model bonus ($10,000) [OV, Prizes]

- "Highest-ranking submission using Gemma E2B or E4B as the base model."
- "Must be one of the team's two selected final submissions."
- LoRA fine-tuning is allowed. Eligible entries stay eligible for the main prizes and the paper track. A daily notebook shows filtered standings.
- **Deadline: Dec 2, 2026, 23:59 UTC.** Host Elan Markowitz, Oct 20, forum thread 751104: "Same submission deadlines apply as the main track prizes." The "Nov 12" date is the paper track's. (`Rules/Verbatim/prizes.md`, `forum-findings.md`)
- **Training data:** trajectories from frontier/closed models are allowed if used "in accordance with their model license terms" and compatible with the winner-license rules (staff, Sep 29, thread 742807). See open-questions Q5 and Rules §2.5, §2.6, §2.8 in `Rules/Verbatim/rules.md`.

## 3. Timeline [OV, Timeline] (all 11:59 PM UTC; "The organizers may update the timeline.")

| Date | Event | As of 2026-11-13 |
|---|---|---|
| Sept 23, 2026 | Start | passed |
| Nov 12, 2026 | Optional research paper deadline | **passed** |
| **Nov 25, 2026** | **Entry deadline (accept rules before this date) and team merger deadline** | 12 days |
| **Dec 2, 2026** | **Final submission deadline** | 19 days |

## 4. Submissions and teams [AUD]

- 1 submission per day; select 2 finals.
- Teams of up to 5; merge before Nov 25. One Kaggle account per person.

## 5. Prizes [OV]

- Main: $37,000 / $18,000 / $10,000.
- Paper Submission Award: $35,000 (paper track, entered separately).
- Small Model Bonus: $10,000.

## 6. Cannot do [AUD: summary of the Rules tab, not verbatim]

- Use any model outside the allowed list, or mix models.
- Use the internet at runtime. L4 sessions must have internet disabled [OV]. L4x4 is only for this competition's notebooks; circumventing that "can lead to team or account bans" [OV].
- Hand-label or hand-predict validation or test data.
- Share code privately outside your team.
- Keep a winning solution closed: winners license under an OSI license (the page says Apache 2.0) and deliver training code, inference code and reproduction steps.
- Use data or tools that aren't reasonably accessible to all, or that cost more than the prize. External data is OK if public or cheap.
- Enter from a sanctioned region (Crimea, DNR, LNR, Cuba, Iran, North Korea). Google/Kaggle staff can enter but cannot win.
- Paper track only: no previously published papers, and 3,000 words maximum.

## 7. Eligibility basics [S]

- Age 18+ or the local age of majority.
