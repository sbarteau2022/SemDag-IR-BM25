<!-- Verbatim copy of every Kaggle staff (ADMIN) and host (HOST) message in both competition forums, oldest first. Fetched 2026-11-13 (UTC) via Kaggle internal API discussions.DiscussionsService (forumIds 11630393 main, 12784402 paper). 420 topics, 1464 messages scanned. Raw JSON in raw/forum/. -->

##### Ashley Oldacre [STAFF/ADMIN] 2026-09-23 | How to get started + Competition's Official Discord | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742815#3527365
### Information for newbies

Welcome! 
**New to machine learning and data science?** No question is too basic or too simple. Feel free to start your own thread, or use this thread as a place to post any first-timer clarifying questions for the Kaggle community to help you with!

**New to Kaggle?** Take a look at a few videos to learn a bit more about [site etiquette](https://www.youtube.com/watch?v=aIus8si_Et0), [Kaggle lingo](https://www.youtube.com/watch?v=sEJHyuWKd-s), and [how to enter a competition using Kaggle Notebooks](https://www.youtube.com/watch?&v=GJBOMWpLpTQ). Publish and share your [models on Kaggle Models](https://www.kaggle.com/docs/models#publishing-a-model)!

**Participants under 18 years old:** If you are under 18 years old and want to participate in this competition, you need to submit a couple of forms:
- Form #1: [Parent/Guardian consent for minor's use of kaggle.com](https://www.kaggle.com/guardian-consent-minor-use). You only have to fill this out once, and it is valid for any competitions on Kaggle. If you already filled this out in the past, you can move on to the next form. 
- Form #2: [Parent/Guardian consent for minor's participation in Kaggle competition](https://www.kaggle.com/consent-minors-process). You have to fill out form #2 for this and any future competitions you want to join. 
Kids under 13 years of age are not allowed to participate on Kaggle. If you have any questions, please leave a comment and we'll follow up with you!

**Looking for a team?** Express your interest in joining a team through our [Team Up](https://www.kaggle.com/discussions/product-feedback/341195) feature.

**Remember**: Kaggle is for everyone. Whether you're teaming up or sharing tips in the competition forum, we expect everyone to follow our Kaggle community guidelines.

### Competition's Official Discord
In addition to this competition forum, you can continue the discussion in our official Kaggle Discord Server here:
# [discord.gg/kaggle](http://discord.gg/kaggle)
 
The Discord is a great place to ask getting started questions, chat about the nuances of this competition, and connect with potential team mates. Learn more about Discord at our [announcement here](https://www.kaggle.com/discussions/general/429933). Here are a few things to keep in mind though:

**1. Discord Competition Channels are 'Public' - Don't Share Private Information**

Discord channels for specific competitions are considered 'public' spaces where you are allowed to talk about competition details. Please remember that private sharing of competition code or data outside of your team is, as always, not permitted. Code sharing must always be done publicly through the Kaggle forums/notebooks.

**2. Discord Competition Channels are Not Monitored by Staff - Keep Important Information on the Kaggle Forums**

Kaggle Staff and Hosts running competitions will not monitor Discord or be available to answer questions in Discord. This is intended to be a more casual space to discuss competitions and help each other. Please keep important questions, insights, writeups, and other valuable conversation on the Kaggle forums. 

Happy modeling! 

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-24 | Two data issues: half the graph/embedding files download empty, and the graphs contain no async functions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742911#3527654
Hi @jasonwold,

Thanks for the report. We will investigate and get back to you.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-24 | Is the swegemma harness available for local evaluation? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742882#3527656
Hi @shimondanziger,

Here is a wheelhouse with the packages: [Gemma 4 Developer Agent Wheelhouse](https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse/data).

I'll post a notebook later today illustrating how to run everything on Kaggle.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-24 | Clarification on distillation from external LLMs | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742807#3527657
Hi @cnumber,

We are confering and will have an answer for you soon.

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-09-24 | Welcome to the Gemma 4 Developer Agent Competition | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743007#3527743
Hello Kagglers,

Today’s most capable software engineering agents rely on massive, closed-source models running in the cloud, leaving advanced autonomous development tools out of reach for many developers.

With Gemma 4, we want to change that.

Our challenge to you is to push the boundaries of open-source models and post-train Gemma 4 into an autonomous coding agent capable of navigating real-world repositories and reliably resolving software engineering tasks on consumer-grade hardware. To help you get started, we’ve provided a [starter submission](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=sample_submission), [development tasks](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=tasks.jsonl), and a corresponding dataset of structured [code graphs](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=graphs) with [pre-computed embeddings](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=embeddings) for repository-level retrieval.

Whether you explore parameter-efficient fine-tuning, novel reinforcement learning approaches, or graph-based code reasoning, we want to see how far you can take local, open models. 

We can't wait to see the agents you build and the solutions you invent!

Google Research and The Gemma Team


##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-09-24 | Welcome to the Gemma 4 Developer Agent Paper Track | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743012#3527751
Hello Kagglers,

Alongside our leaderboard competition, we are excited to launch the Gemma 4 Developer Agent Paper Track! This is a dedicated venue to share original research and advance the state of the art in agentic software engineering.

While the main competition leaderboard tracks how many real-world issues your agent can resolve, the Paper Track invites you to explore the how and why. We welcome original, unpublished research, methodological insights, and detailed project writeups across topics including:
- **Tuning & Optimization:** Parameter-efficient fine-tuning and reinforcement learning tailored for SWE agents.
- **Code Comprehension & Graph Reasoning:** Techniques for parsing, embedding, and reasoning over complex code repositories and graph representations.
- **New Resources & Benchmarks:** Datasets, evaluation suites, and tools for structured code generation and repository understanding.
- **Novel Applications:** Creative use cases leveraging Gemma 4, DiffusionGemma, or code graphs beyond standard benchmarks.

The Paper Track is open to independent research; You do not need to participate in or top the main leaderboard to submit. The top submissions will share a $35,000 prize pool (Best Paper, Best New Resource, and Best New Application) and will be highlighted during a Google hosted event (such as a NeurIPS expo workshop).

We look forward to reading your findings and seeing the ideas you bring to the community!

Google Research and The Gemma Team


##### Ryan Holbrook [STAFF/ADMIN] 2026-09-24 | Scoring-run questions: task concurrency, eval_config keys, and the 12 h limit  | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3527819
1. Sequentially.
2. The scorer reads those, and only those, four fields. The default is no limit.
3. Currently, hitting the 12-hour limit will error, but I'm planning on a fix that will score unfinished tasks as 0. You may want to set `max_time_minutes` to something moderate as a failsafe.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Official sample_submission scores FAILED — are submitted adapters meant to be registered as named LoRA modules? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743213#3528095
Hi @dominicjamil,

I have a fix incoming. Will try to post a demo notebook later today.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Gemma4 allowed variant | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743056#3528134
It's only the one model listed in the Overview. We're working on supporting others.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | The $65k prize is cheaper than the GPUs you need to win it... | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743316#3528212
Hi @lordfirlefans,

Thanks for your feedback. We're working on adding support for the other Gemma 4 dense variants (e2b, e4b, and 12b) and possibly the 26b MoE and diffusion models as well. Those should hopefully be working early next week. We're also providing 4xL4 GPU (4x24GB) machines for competition participants. I hope you'll participate!

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Not able to download data | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743353#3528271
Broken from the Data page, too. I will try re-uploading the dataset. Thanks for the heads up.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Not able to download data | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743353#3528277
That's unlikely, unfortunately.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Is the swegemma harness available for local evaluation? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742882#3528281
It's here: https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Official sample_submission scores FAILED — are submitted adapters meant to be registered as named LoRA modules? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743213#3528298
I'll check again. There might have been a data bundle that didn't catch the update. It's working in the Getting Started notebook, at least.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-25 | Rules: Only LORA allowed? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743383#3528316
Our evaluation system in this competition is only able to accept LoRA adapters.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | LoRA adapters are silently wiped in the patched vLLM 0.19.1 (Gemma4 decoder layers registered twice) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743508#3528725
Thanks for the report. I will address.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | How much of the submission runtime is excluded as patch validation? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743663#3528731
IIRC, patch validation takes around two hours if a patch is submitted for every task. If no patch is submitted for a task, then validation is skipped and that task just scores 0. A "no patch" submission only takes about ten minutes.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | Official sample_submission scores FAILED — are submitted adapters meant to be registered as named LoRA modules? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743213#3528740
Thanks for the report. I think I've resolved this one, but please let me know.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | Two data issues: half the graph/embedding files download empty, and the graphs contain no async functions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742911#3528743
The embeddings are no longer empty; that has been fixed. The missing `async` functions are still missing. I don't have an ETA on that yet.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | How to package and resolve custom Python tools in submission.zip given adk-submission's closed ToolRegistry? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743573#3528747
Include them as scripts in a skill. They will be available in the sandbox and your agent can execute them there.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | Rules: Only LORA allowed? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743383#3528749
It's not against the rules per se, it's just that our system isn't configured to run it. For one, we don't have the GPUs. The system is configured to accept LoRA adapters, so if you tried to submit it, the script would just throw an error. We chose to accept LoRA adapters to allow some amount of finetuning while also keeping submission file sizes moderate and for being more accessible under the hardware people are likely to have access to.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | Is the swegemma harness available for local evaluation? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742882#3528750
Hi @irfanparaniya,

Thanks for the report. I will look into it (likely on Monday). For now, I can verify at least that the evaluation metric correctly validates a gold-patch submission at 100%.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | Rerunning Failed Submissions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743683#3528752
Hi everyone,

Some submissions since yesterday were failing with `"Your notebook has requested more CPU, GPU or TPU resources than are available."` I believe I've resolved the issue, though please let me know if you're still having issues. I will rerun the affected submissions on Monday so that you won't be losing a submission.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-26 | Rerunning Failed Submissions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743683#3528777
Has this submission run successfully in the past? I'm seeing `Did not find output file 'submission.zip' in the submitted Notebook.`

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-27 | Task Verification Question | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743817#3529102
We did much more extensive reviewing and editing of the test tasks than the training tasks. "Impossible" tasks like you've described are one of the things we checked for. We also checked that a failing test case for the frontier model's patch was something it could have gotten correct with the information given. Unfortunately, time and resource constraints meant that we weren't able to do the same kind of review for the training set.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-27 | Which google-adk versions and YAML features does the official evaluator support? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743800#3529108
1. I would take the set of packages in the wheelhouse dataset as the authoritative set of packages for this competition.
2. We do not support for ADK 2.x features for this competition (maybe for future competitions). The scoring environment has a fixed set of packages installed which cannot be modified.
3. The `HARNESS_README.md` has some of this information. Almost any kind of ADK 1.x configuration is allowed, as described in the [Agent Config spec](https://adk.dev/api-reference/agentconfig/). We block anything that allows arbitrary code execution.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-27 | Is the swegemma harness available for local evaluation? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742882#3529110
This may be a problem with the subprocess sandbox. I don't recall seeing these failures using the Docker sandbox. The private Docker sandbox uses the same base image but installs a different set of dependencies because the test issues come from a different set of repos.

I'll look into getting a more reliable setup going in the notebook environment.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-28 | Clarifications on 12h overrun, ParallelAgent concurrency, LoRA loading, and self-generated training data | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743964#3529469
- 12h overrun: Not yet. Budget per task using `eval_config.yaml`.
- Parallel: I we don't support parallel calls.
- LoRA: I applied a fix for LoRA loading yesterday. You can see the limits on rank and size in the getting started notebook and also in the `HARNESS_README.md`. There's also a total submission limit of 3GB.
- Training data: Training on gemma-4-31b itself is fine. We'll try to have an answer for outputs from other models soon.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-28 | Rerunning Failed Submissions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743683#3529541
I think this is WAI. Your notebook needs to generate a submission file (`submission.zip`) before that submission can be scored. The workflow seems a little confusing, though. I will give feedback to the team.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-28 | Rerunning Failed Submissions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743683#3529544
Hi everyone,

I'm going to pause the rescore until we can resolve the queueing for the L4x4 machines. I will get it going as soon as I can.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-28 | Can the scoring server load Gemma 4 LoRA adapters? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744070#3529575
We're using a patched version of vLLM 0.19, updated in the wheelhouse recently. You might try re-downloading or updating your wheelhouse dataset if you haven't recently. The [getting started](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent) notebook appears to show it working.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-29 | Tool results reach the model double-JSON-encoded: a line of code with quotes turns into a wall of backslashes | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744272#3530081
Thanks for the report. Addressing now.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-29 | Does one scoring run cover both hidden partitions (~240 tasks) in the 12-hour window? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744258#3530082
There are ~120 tasks in the test set, or about 60 in each of the public and private splits. They are scored during the same 12-hour run.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-29 | Reference patches fail for most FastAPI tasks in the public sandbox: are hidden tasks filtered? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744259#3530086
The tasks in the test set have been more rigorously filtered. I can confirm that a submission with "gold patches" validates at 100%. We will work on improving the training set.

##### Ashley Oldacre [STAFF/ADMIN] 2026-09-29 | Clarification on distillation from external LLMs | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742807#3530102
Hello and thank you for your question and your patience. As long as you are using those models in accordance with their model license terms, and the output you're using to submit to that competition doesn't 'conflict with the license requirement of the rules of this competition, you may use them. 

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-29 | Thinking mode drops the model's thoughts between tool calls (vLLM ignores `reasoning_content`). Will the scoring environment be patched? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744354#3530145
Thanks for the heads up. Looks like this is a bug/incompatibility in how ADK and vLLM process reasoning tokens. vLLM [fixed](https://github.com/vllm-project/vllm/pull/42664) this in a later version. I'll add a patch accordingly and try to deploy later today. Unfortunately, due to compute constraints, we won't be able to rescore all existing submissions.

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-09-29 | Clarification: number of writeups per team and eligibility across awards | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3530171
Great questions! 
1. A team can submit at most two write-ups. There is only one submission track, and the judges will determine the eligibility for each prize. We are looking for quality over quantity. 
2. Yes. A single write-up can be considered for more than one award, however, it will only be eligible to win one. If it is Best Paper it will win Best Paper and then no longer be eligible for the resource or application prize.
3. The same criteria will be applied to each, but in the context of that prize. Meaning the *novelty, quality, and relevance* will be scored in terms of the new resource or application. 
4. I believe that should be acceptable with citation and with linking to the Kaggle dataset. If you publish new graphs and embeddings that link to the Kaggle dataset, you would not be redistributing the public dataset. I will double check our exact rules on this front. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-09-29 | Clarification for Paper Submission | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743310#3530176
1. The prize winning submissions will be highlighted.
2. Currently, I can only promise the prize winning submissions will be highlighted. 
3. This is non-archival and participants are allowed to submit in parallel to other venues. Parallel submission to ArXiv is also allowed and encouraged (it is even one of the submission options). 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-09-29 | Bug: writeup editing/submission broken - CheckHackathonWriteupConflict returns 404 | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743094#3530177
Is this still affecting you? Or anyone else? 

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-29 | FastApi tasks fail even with the gold patch, typing_inspection seems to be missing | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744370#3530187
I can confirm that the hidden tasks validate at 100% with a "gold patch" submission.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | LoRA adapters are silently wiped in the patched vLLM 0.19.1 (Gemma4 decoder layers registered twice) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743508#3530598
1. The zeroing fix landed in v23 of the wheelhouse dataset (now on v25). You might check that your notebook has the most recent version.
2. Yes, it should. `discover_adapters` expects the submission root, so make sure you're passing that and not the adapter directory.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | LoRA adapters are silently wiped in the patched vLLM 0.19.1 (Gemma4 decoder layers registered twice) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743508#3530599
It should be fixed in the most recent wheelhouse version, but please let me know if it seems otherwise.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | thinking_budget and seed are missing from HTTP requests in my wheelhouse test | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744566#3530630
Hi @veronikayaitskikh,

Thanks for the heads up. I will patch.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | With LoRA enabled, the 4xL4 KV cache shrinks to ~7.6k tokens; requests longer than that hang | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744331#3530648
Thanks for the report. I will patch to set the `loras` parameters based on the submission. It looks like a bug in our vLLM version is causing the hang, but I think I have a workaround.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | Thinking mode drops the model's thoughts between tool calls (vLLM ignores `reasoning_content`). Will the scoring environment be patched? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744354#3530709
It's incoming.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | ONLY ONE search_similar_code call can blow your context up | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744577#3530710
Thanks for the heads up. I will limit to `max_stdout_chars` like other tools. Glad you're liking the graph tools!

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | Compaction can't trigger at token_threshold 32,768, and overflow then discards the patch (follow-up to #743456) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744692#3530752
Thanks, I will look into it.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | thinking_budget and seed are missing from HTTP requests in my wheelhouse test | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744566#3530753
The most recent wheelhouse dataset should have the patches.

##### Ryan Holbrook [STAFF/ADMIN] 2026-09-30 | "'>' not supported between instances of 'int' and 'str'". Is this same for everyone? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744678#3530769
Fix incoming.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | Submission errors after the Sep 30 wheelhouse update | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744807#3531241
We had a GPU outage overnight. Resolved now, and submissions should be working again.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | Thinking mode drops the model's thoughts between tool calls (vLLM ignores `reasoning_content`). Will the scoring environment be patched? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744354#3531244
Yes, this is unambiguously a bug. The fix should be in the current wheelhouse.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | Several harness issues make results hard to trust: request for fixes and a status update | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744794#3531245
- I'll look into the compaction issue.
- The KV-cache drop with LoRA should be addressed. Now vLLM will set its LoRA params dynamically based on what you actually submit. Submitting fewer adapters with lower rank (or no adapters) leaves more memory for KV-cache.
- KV-cache, double-encoded tool output, thoughts dropped, and thinking_budget / seed not sent are all fixed in the latest wheelhouse.
- Hard to estimate as it depends on the tool and how the model responds. You could experiment in a notebook on the training set to try to get estimates.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | Hidden test set | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744951#3531258
No, the test set draws from private repositories not available publicly.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | "'>' not supported between instances of 'int' and 'str'". Is this same for everyone? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744678#3531314
The fix should be in the current wheelhouse. I recommend just updating the packages.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | Tool results reach the model double-JSON-encoded: a line of code with quotes turns into a wall of backslashes | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744272#3531343
The latest wheelhouse should have this fixed.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 | Test-file reset before test_patch is a no-op (git checkout aborts on missing pathspecs) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744825#3531354
Addressing now.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-01 |  undeclared tool ends the task and discards the patch | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745028#3531436
Yes, let me look into it and I'll implement something.

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-05 | Note on Code Graphs for Async Functions | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745998#3533186
There have been a number of discussion posts pointing out that `async def` functions are not included in the code graph tools. This is true and is an issue for some of the public tasks in fastapi and httpx. 

However, it is not an issue for any of the private repo tasks. 

None of the private repo tasks touch any functions defined with `async def`. Additionally, `async def` functions are rare within the private repos as a whole, at most 1.8% of functions. 

As a result, we will not be doing an update to the private tasks' code graphs. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-05 | Does an arXiv preprint count as "published" for the Paper Track? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/745872#3533288
Posting to ArXiv is totally fine! You can even submit a link to the ArXiv paper as your submission. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-05 | Question: does a blog post about a pilot study count as prior publication? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/745150#3533294
Sounds very interesting! That is definitely a valid submission, especially given the recency and extensions you are working on. 

##### Ashley Oldacre [STAFF/ADMIN] 2026-10-05 | Photo Inquiry | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/745326#3533296
Hello @asmaessaedi, yes can opt out of photo publicity. And yes, photos submitted for identity verification are kept completely separate from our marketing materials. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-05 | Clarification: fully AI-assisted resources, individual entrants, and publicity | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/745712#3533328
Answering part 1 for now. Using Codex and other resources is permitted but it is your responsibility to follow terms of service, and make sure you meet all the submission requirements of the competition. Use of coding assistants to generate code is absolutely acceptable (might I suggest [Google Antigravity](https://antigravity.google/?gclsrc=aw.ds&gad_source=1&gad_campaignid=24305882099&gbraid=0AAAABE0JD34jHPiqeC-djohaiMSRUzZ2_&gclid=CjwKCAjwlY3WBhANEiwApsNrLd4MKkUq0v6gcGwp00k6GxsdtwY5Ctp8jDqrun3I_i8Zu5NXb6Ga8RoCZ1YQAvD_BwE) ).

I would caution against relying solely on LLMs for the written part. Purely LLM generated "slop" will not score well. However, if tastefully used, LLMs can improve the writing quality and clarity. 

We will have an answer for the other questions shortly. 

##### Ashley Oldacre [STAFF/ADMIN] 2026-10-05 | Clarification: fully AI-assisted resources, individual entrants, and publicity | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/745712#3533329
Hello @Trekas, 
To answer the following  2 questions: 
2) Yes, individual Kagglers can receive a prize if they are unaffiliated with a company
3) Yes, we are able to make reasonable accommodations around using your likeness in the event you are selected as a winner.

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-05 | Allowed training data for LoRA adapters: trajectories from other open models? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746046#3533331
Both cases are permitted. 

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-07 | 60 tasks or 120 tasks | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746008#3534190
We considered this here and have done so in the past (e.g., AIMO 3). We opted for the full evaluation during submission time here because of the complexity of the tasks and the increased risk of submission errors. What we don't want to happen is a lot of submissions that succeed on the public split, but error on the private split. Running  submissions on all of the tasks each time means that if your submission succeeds at all (you get a public LB score), you know that it succeeded on the private split too.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-07 | Scoring-run questions: task concurrency, eval_config keys, and the 12 h limit  | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3534253
I'm reconsidering this request. The trouble is that we run both the public and the private tasks during the same 12 hour evaluation, and it's not clear to me yet how to support assigning 0 to unfinished tasks in a way that's fair and consistent.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-07 | Aggregated questions from what has generally been asked on the forum : HOSTS ANSWER PLEASE | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745805#3534268
1. I'm reconsidering this request. The trouble is that we run both the public and the private tasks in the same 12 hour evaluation, and it's not clear to me yet how to assign 0 to unanswered tasks in a way that's fair and consistent.
2. I will likely make this configurable in a future update.
3. I will double check this and fix if necessary. Patch verification generally shouldn't timeout.
4. I didn't observe any significant command overhead compared to a plain container.
5. Both public and private tasks are evaluated during the same 12 hour run.
6. Yes.
7. Probably not. Information like this makes it too easy to extract information about the test set through probing.
8. I'm working on support for other models. We will retain the restriction to one model type per submission however (no main 31b agent and 12b subagent, for instance). Memory management on the L4x4s is too complex trying to support multiple models per run.
9. The test-file reset fix will be live soon.
10. A fix for bad tool calls will also be live soon.


##### Dustin [STAFF/ADMIN] 2026-10-08 | submission is running for 15h. is this due to evaluation ? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746480#3535567
Please see: https://kaggle.com/competitions/gemma-4-developer-agent/discussion/747519

##### Dustin [STAFF/ADMIN] 2026-10-08 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3535572
Hi everyone,

I wanted to give an update on the long submission wait times and "Kaggle Error" failures many of you have been seeing over the past couple of days.

## What Happened

Due to very high submission volume using L4s, submission jobs have been facing long queue times before actually getting a machine to run. Submissions that waited \>15h to start were being marked as “Kaggle Error” even if they eventually did run.

## What We Fixed

1. **Extended Queue Timeout:** We've drastically extended the queue allowance so submissions will no longer be timed out while waiting to run.  
2. **Scoring Submissions that had Queue Timeouts:** We are actively reprocessing all affected submissions from the past few days. If your notebook ran to completion and produced a valid submission file, it is being scored and published to the leaderboard automatically. You should already see scores showing up on the leaderboard now.  
3. **Queue Wait Times:** to even some of the load on the pool, we are implementing a pending submission limit (separate from the 1/day limit). If your team's previous submission is still scoring, you will need to wait until it finishes to submit again.

## What This Means for You

* **No action needed:** You do not need to resubmit or contact support to recover an affected run; our batch recovery is processing them directly.  
* **Monitor this post for updates**

Thanks for your patience while we sort this out, and sorry for the frustration it caused over the last few days.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-09 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3535942
It's possible, yes, that you will lose a daily submission this way. Unfortunately, even after doubling the number of L4 machines, we were still seeing the queue grow without bounds. Since, at the moment, it doesn't look like we'll be able to increase our supply of GPUs, we have to reduce somehow the submission demand instead.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-09 |  fastapi tasks can't pass even with the gold patch | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747248#3535945
Hi @mkrimenurgm, I'm working on fixing up the set of training tasks. None of the repos in the training tasks are present in the test set, however. I can verify that every task in the test set is solvable and validates at 100% with a "gold patch" submission.

##### Dustin [STAFF/ADMIN] 2026-10-09 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3535953
Additionally, if you're in this boat, everyone is, so while it's understandably frustrating, it is fair. That's why giving more subs won't help, since it'll just mean even longer wait times.

##### Dustin [STAFF/ADMIN] 2026-10-09 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3535991
Currently, the queue is very long, however the recent submission limit that we introduced has bounded queue growth, and the queue is draining very slowly.

If the number of teams actively submitting doesn't drastically increase, the queue should stabilize back down to the "daily" submission rate (where each run starts and finishes within the same day), though it may take ~a week for that to happen since there is a backlog to burn down.

##### Dustin [STAFF/ADMIN] 2026-10-09 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3536170
I think Ryan covers that in this comment:
https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3535930

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-10 | Wheelhouse v29/v30: include_thoughts: false no longer disables thinking (thinking_budget: 0 does) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747914#3536450
This was intended. My apologies. I'll post an update on Monday and update the readme. This change was meant to have `include_thoughts` manage what's carried in the chat template from call to call, more consistent with the Gemini API.

##### Dustin [STAFF/ADMIN] 2026-10-10 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3536532
The current queue delay is around ~33h, so yes, your submission isn't stuck, its making its way towards the front of a long line of submissions. If its been >33h, its likely running right now and your score will arrive once it finishes, scores have continued to work its just incredibly high demand and finite supply.

Thanks for your patience everyone, we will continue to do what we can.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-11 | Wheelhouse v29/v30: include_thoughts: false no longer disables thinking (thinking_budget: 0 does) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747914#3536860
Thanks for the heads up. I haven't tested the change yet with `transformers serve`. It should work with vLLM, though. I'll investigate.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-11 | New Gemma 4 Models Available: 12B, E4B, and E2B | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3536861
Hi everyone,

We've added support for [several smaller Gemma 4 variants](https://www.kaggle.com/models/google/gemma-4/other/). You can now use any of the following models for your agents:
- `gemma-4-31b-it-qat-w4a16-ct`
- `gemma-4-12b-it-qat-w4a16-ct`
- `gemma-4-e4b-it-qat-w4a16-ct`
- `gemma-4-e2b-it-qat-w4a16-ct`

We don't support mixing variants within a submission, however. Every agent and subagent in your submission must use the same variant (though they can attach different LoRA adapters.)

These smaller models open up some new strategies:
1. **More test time compute:** Inference is faster and memory burden lower so you can execute more and longer reasoning turns and iteration cycles. You could also experiment with using `ParallelAgent` for concurrent LLM calls (though tool calls are still executed sequentially).
2. **Faster and more accessible LoRA finetuning:** Experiment with different setups more quickly and on more accessible GPUs. We provide L4x4s for use in interactive notebooks, but adapters can now be finetuned on a wider variety of consumer hardware.
3. **More specialized agents:** Smaller models use smaller LoRA adapters, so you can include more of them in your submission.

We're excited to see what you build!

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-11 | New Gemma 4 Models Available: 12B, E4B, and E2B | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3536939
I'll update the Getting Started notebook on Monday to illustrate. The tl;dr is that you need to add:

```
MODEL_VLLM_EXTRA_ARGS: dict[str, tuple[str, ...]] = {
    'gemma-4-12b-it-qat-w4a16-ct': (
        '--hf-overrides',
        '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}',
    ),
}
```
and 
```
cfg = VllmConfig(
    ...
    extra_args=MODEL_VLLM_EXTRA_ARGS.get(chosen_model, ()),
)
```

The scorer has this update already. 

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-11 | New Gemma 4 Models Available: 12B, E4B, and E2B | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3536990
Ah, okay, good catch. I think it's too risky to attempt a migration to ADK v2 at this point, but good to know.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-11 | New Gemma 4 Models Available: 12B, E4B, and E2B | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3536992
1. Yes, everything is the same.
2. The unquantized variants are on the same page: [Gemma 4](https://www.kaggle.com/models/google/gemma-4/transformers).

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-12 | A few scoring-setup questions, so we can test offline and lean less on the queue | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748428#3537307
Hi @johnsoliva,

Thanks for the questions. The discussion board has been busy, and I've missed a few posts.

1. A participant's `eval_config.yaml` doesn't affect scoring. The only thing the scorer gets are the submitted patches. The `pytest` run in the scorer gets a timeout of 300 seconds to prevent hung tests from killing the whole submission. The gold patches finish well within this time.
2. It's the same sandbox but different wheels.
3. Yes, fail before gold patch and pass after. There are a variety of repos of varying sizes and domains. Some repos have more tasks than others. The tasks were filtered by running a strong commercial on them with a simple config and keeping only those tasks it either succeeded at or failed by one assertion (typically some solvable edge case).
4. Yes, I will try to be better about this.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-12 | A few scoring-setup questions, so we can test offline and lean less on the queue | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748428#3537362
Yes, the `eval_config.yaml` applies when the agent is running.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-12 | A few scoring-setup questions, so we can test offline and lean less on the queue | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748428#3537380
1. There is no network timeout delay during container setup.
3. Yes, it can run pytest in its sandbox.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-12 | Updating the Gemma 4 template to have July 15th fixes | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744844#3537388
I will investigate!

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-12 | A few scoring-setup questions, so we can test offline and lean less on the queue | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748428#3537459
Yes, you can rely on the package under test (and its pre-cached test dependencies) being importable in-place in both the agent sandbox and the verification sandbox.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-12 | New Gemma 4 Models Available: 12B, E4B, and E2B | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3537606
Fixed in the most recent wheelhouse. Thanks for the heads up.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-13 | [Fixed] Unable to download data. | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748890#3538061
Please check again. I reuploaded the data, and I think it's working now.

##### Dustin [STAFF/ADMIN] 2026-10-13 | Update on "Kaggle Error" Submissions & Queue Delays | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3538109
Update: Queue delay has fallen to around ~14h, its *slowly* going down, but most runs should finish within ~24hish of submit now.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-14 | Constantly facing "Notebook threw Exception" | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749200#3538603
Hi @nerdayan,

It looks like your submission is failing because the zip contains a Python bytecode cache file (`.pyc`), which are not files accepted by the scorer.

I apologize for the confusing error message. We'll work on improving these. The "Notebook threw Exception" error you're seeing is from the scoring script, which runs in a Kaggle notebook. It was the scoring script that threw the exception when it encountered the `.pyc` file.


##### Ryan Holbrook [STAFF/ADMIN] 2026-10-15 | LoRA adapter loads and is served, but has no effect on outputs (current wheelhouse, 4×L4) – repro inside | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749528#3539167
Hi @anantsharma25,

Here is my agent's analysis. tl;dr is that the adapters are being applied correctly. You probably just need to apply an adapter to more layers to see a change in outputs. The sample submission just applies it to layer 0.

---

Good news: **your logprob numbers actually confirm that your LoRA adapters are loaded and active in the forward
  pass**, and the scoring environment uses the exact same patched vLLM 0.19.1 wheelhouse.

Here is why replacing `lora_A` and `lora_B` in `sample_submission` with $\mathcal{N}(0, 0.5)$ (or even
  $\mathcal{N}(0, 100)$) only changes the top-1 logprob from `-7.4e-06` to `-3.7e-05` without changing the greedy
  text:

### 1. Why `-7.4e-06` vs `-3.7e-05` vs `-2.3e-05` is a ~1.6-unit raw logit shift (not numerical noise)
At `temperature=0`, vLLM greedy decoding is bit-for-bit deterministic (`0` difference across runs when weights are unchanged). The reason the shift looks like `~1e-5` on the top token `"2"` is **softmax saturation**:
- `logprobs` returns $\ln \text{softmax}(z)_1$, not the raw logit $z_1$.
 - When $p_1 \approx 1 - 7.4\times 10^{-6} = 0.9999926$, the logit margin between `"2"` and the runner-up token
  is $z_1 - z_2 \approx -\ln(7.4\times 10^{-6}) = \mathbf{11.81}$.
- With `main_lora` ($\ln p_1 = -3.7\times 10^{-5}$), the logit margin drops to $-\ln(3.7\times 10^{-5}) =
  \mathbf{10.20}$ — a **1.61-unit shift in the raw logits** (and a **5×** change in $1 - p_1$).
- With `tool_lora` ($\ln p_1 = -2.3\times 10^{-5}$), the logit margin shifts to $\mathbf{10.68}$ (**1.13 raw
  logit units**).
- Because $\frac{\partial \ln p_1}{\partial z_1} = 1 - p_1 \approx 10^{-5}$ when $p_1 \approx 1$, an $O(1)$ shift in raw logits looks like $O(10^{-5})$ on the top-1 logprob, while the runner-up token logprobs (`top_logprobs=5`) shift by the full ~1.1–1.6 nats.

### 2. Why large random weights in `sample_submission` don't blow up the output
`sample_submission/adapters/main_lora/adapter_config.json` is a minimal 1-layer smoke-test stub with `"layers_to_transform": [0]` and `"target_modules": ["q_proj", "o_proj"]` — it only contains weights for **Layer 0** out of **60 layers**.

Unlike Llama/Qwen (where `o_proj` is added directly to the residual stream, so multiplying Layer 0 `o_proj` by a large number explodes the residual stream), **Gemma 4 uses Sandwich-RMSNorm + Q-RMSNorm**:
1. Immediately after `qkv_proj`, `q` passes through per-head `self.q_norm` (`RMSNorm`).
2. Immediately after `o_proj`, the attention output passes through `self.post_attention_layernorm` (`RMSNorm`)
**before** being added to `residual`:
       ```python
       hidden_states = self.self_attn(positions=positions, hidden_states=hidden_states, **kwargs)
       hidden_states = self.post_attention_layernorm(hidden_states)
       hidden_states = hidden_states + residual
       ```

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-15 | Question about LoRA | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749191#3539170
Hi @niraberman,

You might check the Getting Started notebook. It uses the same configuration as the scorer. The key setting for you I think is `os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'`. We have seen successful submissions with LoRA adapters up to rank 64.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-15 | Getting Started notebook fails: wheelhouse is cp312 but environment is Python 3.13 / torch 2.11 | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749505#3539175
Try starting from a direct fork of the Getting Started notebook. It should still be pinned to the original Python 3.12 image.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-15 | Could the 12 h be one budget for the whole run, instead of a per-task cap? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749597#3539198
Hi @vaibhavnakrani,

Thanks for bringing this up. Naively setting unfinished tasks to 0 could lead to inconsistent results on the public and private leaderboards. I will try to think of other ways we could allow teams to better utilize the 12 hours, though.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-15 | New Gemma 4 Models Available: 12B, E4B, and E2B | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287#3539249
Will do, thanks!

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-16 | Request: publish top-agent episode/replay datasets (as in Orbit Wars / Pokémon TCG) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/749953#3539810
Hi @astraeusdotdev,

It's an interesting idea! And you're right that while we do publish replays for agents in our simulation competitions, there's nothing similar for traditional competitions. Unfortunately, I don't think this will be possible, at least for this competition, since publishing the replays on the test set would also publish significant parts of the test set itself. (In fact, someone could use published traces to intentionally exfiltrate all or most of the test data.)

I do like the idea though. Perhaps something similar could work with a different setup.

##### Ryan Holbrook [STAFF/ADMIN] 2026-10-16 | How to package and resolve custom Python tools in submission.zip given adk-submission's closed ToolRegistry? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743573#3539965
Your agent will discover them automatically per the [ADK skills feature](https://adk.dev/skills/#system-instructions-for-using-skills).

##### Ashley Oldacre [STAFF/ADMIN] 2026-10-19 | Bug Report with 5 Issues | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/750753#3541339
Thanks for bringing this to our attention! We are working on this. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-20 | 🌟Bonus Prize: Small Model Development ($10,000) | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751104#3541749
We are offering an additional **$10,000 bonus prize** dedicated to small-footprint developer agents:

- **Award:** $10,000 to the highest-ranking submission utilizing **Gemma E2B** or **Gemma E4B**. Final scores are based on the private test set performance. Same submission rules and tie-breaking apply.

- **Eligibility:** Submissions must explicitly use either Gemma E2B or Gemma E4B as the base model. For a submission to be eligible it must be one of the team’s two selected final submissions. LoRA fine-tuning is allowed just as done for the main track. 

- **Daily Leaderboard Tracking:** A [separate Kaggle notebook](https://www.kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard) will be released and updated daily to display public standings for eligible small model entries. 

- **Cross-Track Eligibility:** Submissions eligible for the Small Model Prize remain fully eligible for general leaderboard awards and the Paper Track.

- **Deadline:** Same submission deadlines apply as the main track prizes. 



##### Ryan Holbrook [STAFF/ADMIN] 2026-10-22 | "Notebook Threw Exception" on a non-LoRA submission that validates and compiles locally | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751339#3542818
Hi @sultanfawad and everyone,

This looks like a failure on our side. We're investigating the root cause and will rerun any submissions that failed on account of it.

Our apologies for the incident.

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-24 | Two Final Submissions: is the private score the better of the two? | https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/752220#3543771
It is the better of the two private leaderboard scores. There’s no downside to selecting a second submission.

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Precision about public notebook and papers vs conflicting Coding Competition | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/752667#3545640
The code itself is not a requirement for submitting the paper if you want to protect it until the main competition ends. Unfortunately the papers will take longer to score which is why the deadline is slightly earlier. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Clarification on Prize Track Categorization, Tie-Breaker Timestamps, and Notebook Runtime | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/750338#3545656
All submissions are considered across all tracks but you are welcome to make it explicit if you prefer! 

Our internal process will involve multiple judges for the top papers so we anticipate ties being extremely unlikely. We can always add more judges to get a more refined score. If it does come to a tie break, it would likely be by original submission time, but again, we will prefer to avoid that. 

The full pipeline does not need to run when doing run all. We will likely look at any code that is present, but running the code itself is not guaranteed to be part of the evaluation process. With that being said, having a quick way to run your code sounds like a good idea to me. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Clarification: number of writeups per team and eligibility across awards | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3545666
All words of the "judged" text count towards the word count including captions and tables (but not figures and references). We do not yet have an official word counter released. If the paper relies on mathematical proofs, please include those or shortened versions in the main paper. Supplementary material not count towards the word limit. 

In the case of a PDF submission, we will just be judging the PDF as the writeup. Recommend using the Kaggle writeup as an abstract. However, it will not be used for judging and will not count towards the word count. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Clarification: number of writeups per team and eligibility across awards | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3545670
Yes regenerated graph files is allowable with appropriate licensing. 

Word limit includes table and captions but not figures and references. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Clarification: number of writeups per team and eligibility across awards | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3545672
Yes, it can include such traces. Please cite and reference the upstream license for the data. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Clarification: number of writeups per team and eligibility across awards | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3545675
The PDF will have the same word limit. All "judged" text is included in the word count except figures and references. The PDF will be judged on its own, ignoring the kaggle writeup component. But yes, title and abstract will, captions, and tables will count towards the word count. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Clarification: number of writeups per team and eligibility across awards | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/743255#3545676
Yep can confirm!

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Non-fancy SFT idea is cool? + Private dataset until main track is over? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/751413#3545680
If necessary, you can release the full dataset after the main track. Since paper judging will begin before that, one option is to release a small sample of the dataset immediately for judging (e.g. 5% random sample of sequences). 

That way the competition stays fair and the evaluation of the resource can also be done in a verifiable way. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Rule 3.6.b: does the code-sharing requirement apply to this paper track? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/751804#3545687
Github should work for sharing code. 

You should not be breaking any permissions to compete in this competition. If you have the rights to evaluate on the external dataset that should be fine. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Permitted independent validation for Paper Track research | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/751403#3545692
Yes, that should be fine. Independent reviewers should be fine to use for the paper track. Just make sure they follow the licensing rules of the competition itself. No restrictions on reporting aggregate results. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Word Count | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/749546#3545695
References will not count. Appendix will not be used for main evaluation so treat is as supplementary material. I.e. can support verifiability like code release but do not expect it to be read guaranteed.  

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Can derived localization labels from the task data be published (paper track)? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/749803#3545696
Yes, publishing derived labels is okay. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-10-27 | Prize eligibility if winners cannot attend the Google-hosted event in person? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/749463#3545699
Prize eligibility is unaffected. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-11-03 | Can derived localization labels from the task data be published (paper track)? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/749803#3549536
I believe the preferred method would be publish the translations keyed by instance_id and link to the original dataset for the verbatim components (or via a script that downloads it). 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-11-04 | Does a public repo count as prior publication for the Paper Track? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/755867#3550169
Prior github repo would not count as a prior publication. So yes, eligible. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-11-04 | Paper Track: licences in a public notebook | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/753871#3550171
1. I believe this rule just covers your code. 
2. I believe a public notebook can call them as they are. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-11-04 | 27 fastapi tasks cannot pass in the provided sandbox (missing inline_snapshot and dirty_equals) | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/753370#3550172
The scoring is done on private repos so does not include these tasks. Also, this is probably a better post for the code track rather than the paper track discussion :)

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-11-09 | Two writeups per team: can both be submitted at the same time? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/753195#3552588
This should be fixed. I see multiple submissions from the same team so should not be an issue. 

##### Elan Markowitz [CONTRIBUTOR/HOST] 2026-11-10 | May we publish a derived PatchGraph-QA JSONL (graph-relative Q&A) for the Paper Track? | https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/757562#3553006
1. Yes, that is fine. Releasing the derived data only with linking via task id metadata is perfect. 
2. Yes, that is okay!
3. If it is just for verification/reproducibility that is fine. (1) is okay so should not be a problem either way. 
4. Yes, that is fine, too. However, (1) is allowed and is probably preferable. 