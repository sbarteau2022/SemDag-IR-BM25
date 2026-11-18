# vllm-metal 0.33.0 / vLLM 0.33.0: `vllm serve` flag inventory

Source: `vllm serve --help=all` on this Mac (raw: `vllm_serve_help_all.txt`, parsed: `flags.json`). **320 flags in 18 groups.** Defaults are vLLM 0.33.0 defaults as printed; the scorer's vLLM version is not published, so its defaults may differ.

Parity column: **SCORER-SET** = passed by the scoring notebook (`adk_submission/server.py` `VllmServer.build_cmd`); **SCORER-DEFAULT** = not passed, so the default decides scorer behaviour; blank = no bearing found on the scorer path.

## Scorer-relevant flags

| flag | default here | parity |
|---|---|---|
| `--model` | `Qwen/Qwen3-0.6B` | SCORER-SET (ct checkpoint; here: lossless MLX repack) |
| `--host` | `None` | SCORER-SET 127.0.0.1 |
| `--port` | `None` | SCORER-SET 8000 (here 8124) |
| `--max-model-len` | `None` | SCORER-SET 32768 |
| `--dtype` | `auto` | SCORER-SET auto |
| `--gpu-memory-utilization` | `0.92` | SCORER-SET 0.90 (Metal sizes its own pool; not passed) |
| `--tensor-parallel-size` | `1` | SCORER-SET 4 (N/A: one Apple GPU) |
| `--enable-auto-tool-choice` | `False` | SCORER-SET |
| `--tool-call-parser` | `None` | SCORER-SET gemma4 |
| `--reasoning-parser` | `` | SCORER-SET gemma4 |
| `--reasoning-config` | `None` | SCORER-SET {<|channel>,<channel|>} |
| `--scheduler-reserve-full-isl` | `True` | SCORER-SET --no- |
| `--enable-lora` | `None` | SCORER-SET if adapters |
| `--max-loras` | `1` | SCORER-SET = number of adapters |
| `--max-lora-rank` | `16` | SCORER-SET = largest adapter rank (default here 16!) |
| `--lora-modules` | `None` | SCORER-SET name=path per adapter |
| `--generation-config` | `auto` | SCORER-DEFAULT auto -> temp 1.0/top_k 64/top_p 0.95 fill unset request fields |
| `--override-generation-config` | `{}` | SCORER-DEFAULT {} |
| `--seed` | `0` | SCORER-DEFAULT 0 |
| `--max-num-seqs` | `None` | SCORER-DEFAULT (platform default; batching width) |
| `--max-num-batched-tokens` | `None` | SCORER-DEFAULT (platform default) |
| `--enable-prefix-caching` | `None` | SCORER-DEFAULT (platform default) |
| `--enable-chunked-prefill` | `None` | SCORER-DEFAULT (platform default) |
| `--kv-cache-dtype` | `auto` | SCORER-DEFAULT auto |
| `--chat-template` | `None` | SCORER-DEFAULT (checkpoint chat_template.jinja) |
| `--served-model-name` | `None` | SCORER-DEFAULT (= --model; harness maps alias -> openai/<served>) |
| `--logits-processors` | `None` | SCORER-DEFAULT None (thinking budget uses the built-in processor) |
| `--async-scheduling` | `None` | SCORER-DEFAULT (platform default) |
| `--default-chat-template-kwargs` | `None` | SCORER-DEFAULT None (harness sends enable_thinking per request) |
| `--speculative-config` | `None` | SCORER-DEFAULT None |
| `--quantization` | `None` | SCORER-DEFAULT None (compressed-tensors auto-detected) |
| `--hf-overrides` | `{}` | SCORER-DEFAULT {} (only 12B gets one) |

Resolved values on this Mac (engine config line in the serve log, 2026-11-17): `enable_prefix_caching=True`, `enable_chunked_prefill=True`, `max_num_batched_tokens=2048`, `kv_cache_dtype=auto`, `seed=0`. The scorer's resolved values on 4×L4 are not observed. Read them from its server log on the gated Kaggle timing run.

## vllm-metal environment variables

`VLLM_METAL_BACKEND, VLLM_METAL_BUILD_FROM_SOURCE, VLLM_METAL_COMPILED_MLP, VLLM_METAL_DECODE_PIPELINE, VLLM_METAL_DISABLE_GQA_DECODE, VLLM_METAL_DISABLE_NAX, VLLM_METAL_GDN_LAZY_KERNELS, VLLM_METAL_KV_COMMIT_PROBE, VLLM_METAL_MLA_KERNEL, VLLM_METAL_MM_PREFIX_PATH, VLLM_METAL_MODELSCOPE_CACHE, VLLM_METAL_MULTIMODAL_MODE, VLLM_METAL_NATIVE_SAMPLING, VLLM_METAL_NAX_GQA_PREFILL, VLLM_METAL_RING_BASE_PORT, VLLM_METAL_SPEC_INGEST_CHUNK, VLLM_METAL_SPEC_VERIFY_WINDOW, VLLM_METAL_TQ_PREFILL, VLLM_METAL_TQ_PREFILL_MAX_MIB, VLLM_METAL_VISIBLE_DEVICES, VLLM_MLX_DEVICE` (from `vllm_metal/envs.py`)

## Full inventory

### options (12)

| flag | default |
|---|---|
| `--aggregate-engine-logging` | `False` |
| `--api-server-count` | `None` |
| `--config` | `None` |
| `--disable-log-stats` | `None` |
| `--enable-log-requests` | `DEBUG` |
| `--fail-on-environ-validation` | `False` |
| `--gdn-prefill-backend` | `None` |
| `--grpc` | `False` |
| `--headless` | `False` |
| `--kda-decode-backend` | `None` |
| `--kda-prefill-backend` | `None` |
| `--shutdown-timeout` | `0` |

### Frontend (62)

| flag | default |
|---|---|
| `--allow-credentials` | `False` |
| `--allowed-headers` | `['*']` |
| `--allowed-methods` | `['*']` |
| `--allowed-origins` | `[]` |
| `--anthropic-disabled-thinking-effort` | `auto` |
| `--api-key` | `None` |
| `--chat-template` | `None` |
| `--chat-template-content-format` | `auto` |
| `--cohere-format` | `cmd4` |
| `--cohere-is-reasoning-model` | `True` |
| `--data-parallel-supervisor-port` | `9256` |
| `--default-chat-template-kwargs` | `None` |
| `--disable-access-log-for-endpoints` | `None` |
| `--disable-fastapi-docs` | `False` |
| `--disable-uvicorn-access-log` | `False` |
| `--dp-supervisor-probe-failure-threshold` | `3` |
| `--dp-supervisor-probe-interval-s` | `5.0` |
| `--dp-supervisor-probe-timeout-s` | `5.0` |
| `--enable-auto-tool-choice` | `False` |
| `--enable-flash-late-interaction` | `True` |
| `--enable-force-include-usage` | `False` |
| `--enable-log-deltas` | `True` |
| `--enable-log-outputs` | `False` |
| `--enable-offline-docs` | `False` |
| `--enable-per-request-metrics` | `False` |
| `--enable-prompt-tokens-details` | `False` |
| `--enable-request-id-headers` | `False` |
| `--enable-scale-out` | `False` |
| `--enable-server-load-tracking` | `False` |
| `--enable-ssl-refresh` | `False` |
| `--enable-tokenizer-info-endpoint` | `False` |
| `--exclude-tools-when-tool-choice-none` | `False` |
| `--fingerprint-mode` | `full` |
| `--fingerprint-value` | `None` |
| `--grpc-port` | `None` |
| `--h11-max-header-count` | `256` |
| `--h11-max-incomplete-event-size` | `4194304` |
| `--host` | `None` |
| `--log-error-stack` | `False` |
| `--lora-modules` | `None` |
| `--max-log-len` | `None` |
| `--middleware` | `[]` |
| `--port` | `None` |
| `--reasoning-effort-map` | `None` |
| `--response-role` | `assistant` |
| `--return-tokens-as-token-ids` | `False` |
| `--root-path` | `None` |
| `--sse-keep-alive-interval` | `0` |
| `--ssl-ca-certs` | `None` |
| `--ssl-cert-reqs` | `0` |
| `--ssl-certfile` | `None` |
| `--ssl-ciphers` | `None` |
| `--ssl-keyfile` | `None` |
| `--tokens-only` | `False` |
| `--tool-call-parser` | `None` |
| `--tool-parser-plugin` | `` |
| `--tool-server` | `None` |
| `--tool-strict-level` | `None` |
| `--trust-request-chat-template` | `False` |
| `--trust-request-mm-kwargs` | `False` |
| `--uds` | `None` |
| `--uvicorn-log-level` | `info` |

### ModelConfig (47)

| flag | default |
|---|---|
| `--allow-deprecated-quantization` | `False` |
| `--allowed-local-media-path` | `` |
| `--allowed-media-domains` | `None` |
| `--code-revision` | `None` |
| `--config-format` | `auto` |
| `--convert` | `auto` |
| `--disable-cascade-attn` | `None` |
| `--disable-sliding-window` | `False` |
| `--dtype` | `auto` |
| `--enable-cumem-allocator` | `False` |
| `--enable-nccl-comm-suspend` | `False` |
| `--enable-prompt-embeds` | `False` |
| `--enable-return-routed-experts` | `False` |
| `--enable-sleep-mode` | `False` |
| `--enable-trace-replay` | `False` |
| `--enforce-eager` | `False` |
| `--generation-config` | `auto` |
| `--hf-config-path` | `None` |
| `--hf-overrides` | `{}` |
| `--hf-token` | `None` |
| `--io-processor-plugin` | `None` |
| `--logits-processors` | `None` |
| `--logprobs-mode` | `raw_logprobs` |
| `--max-logprobs` | `20` |
| `--max-model-len` | `None` |
| `--model` | `Qwen/Qwen3-0.6B` |
| `--model-class-overrides` | `{}` |
| `--model-impl` | `auto` |
| `--override-generation-config` | `{}` |
| `--pooler-config` | `None` |
| `--quantization` | `None` |
| `--quantization-config` | `None` |
| `--renderer-num-workers` | `1` |
| `--return-sampling-mask` | `False` |
| `--revision` | `None` |
| `--runner` | `auto` |
| `--seed` | `0` |
| `--served-model-name` | `None` |
| `--skip-tokenizer-init` | `False` |
| `--sleep-mode-backend` | `cumem` |
| `--sleep-mode-offload-cudagraph` | `False` |
| `--sleep-preserve-parameter-names` | `[]` |
| `--tokenizer` | `None` |
| `--tokenizer-mode` | `auto` |
| `--tokenizer-revision` | `None` |
| `--trust-remote-code` | `False` |
| `--use-fp64-gumbel` | `False` |

### LoadConfig (9)

| flag | default |
|---|---|
| `--download-dir` | `None` |
| `--ignore-patterns` | `['original/**/*']` |
| `--load-format` | `auto` |
| `--model-loader-extra-config` | `{}` |
| `--pt-load-map-location` | `cpu` |
| `--safetensors-load-strategy` | `None` |
| `--safetensors-prefetch-block-size` | `16777216` |
| `--safetensors-prefetch-num-threads` | `8` |
| `--use-tqdm-on-load` | `True` |

### AttentionConfig (1)

| flag | default |
|---|---|
| `--attention-backend` | `None` |

### MambaConfig (4)

| flag | default |
|---|---|
| `--enable-mamba-cache-stochastic-rounding` | `False` |
| `--mamba-backend` | `MambaBackendEnum.TRITON` |
| `--mamba-cache-philox-rounds` | `0` |
| `--mamba-ssu-algorithm` | `None` |

### StructuredOutputsConfig (2)

| flag | default |
|---|---|
| `--reasoning-parser` | `` |
| `--reasoning-parser-plugin` | `` |

### ParallelConfig (53)

| flag | default |
|---|---|
| `--all2all-backend` | `allgather_reducescatter` |
| `--cp-kv-cache-interleave-size` | `None` |
| `--cpu-distributed-timeout-seconds` | `None` |
| `--data-parallel-address` | `None` |
| `--data-parallel-backend` | `mp` |
| `--data-parallel-external-lb` | `False` |
| `--data-parallel-hybrid-lb` | `False` |
| `--data-parallel-multi-port-external-lb` | `False` |
| `--data-parallel-rank` | `None` |
| `--data-parallel-rpc-port` | `None` |
| `--data-parallel-size` | `1` |
| `--data-parallel-size-local` | `None` |
| `--data-parallel-start-rank` | `None` |
| `--dbo-decode-token-threshold` | `32` |
| `--dbo-prefill-token-threshold` | `512` |
| `--dcp-comm-backend` | `None` |
| `--dcp-kv-cache-interleave-size` | `1` |
| `--dcp-q-replicate` | `None` |
| `--decode-context-parallel-size` | `1` |
| `--device-ids` | `None` |
| `--disable-custom-all-reduce` | `False` |
| `--disable-nccl-for-dp-synchronization` | `None` |
| `--distributed-executor-backend` | `None` |
| `--distributed-timeout-seconds` | `None` |
| `--dp-sync-interval` | `16` |
| `--elastic-ep-max-dp-size` | `None` |
| `--enable-batch-sharded-sampling` | `None` |
| `--enable-dbo` | `False` |
| `--enable-elastic-ep` | `False` |
| `--enable-ep-weight-filter` | `False` |
| `--enable-eplb` | `False` |
| `--enable-expert-parallel` | `False` |
| `--enable-fault-tolerance` | `False` |
| `--enable-hc-sp` | `False` |
| `--enable-shm-tensor-arena` | `False` |
| `--eplb-config` | `EPLBConfig(window_size=1000, step_interval=3000, num_redundant_experts=0, log_balancedness=False, log_balancedness_interval=1, use_async=True, policy='default', communicator=None, enable_migration_batching=False` |
| `--expert-placement-strategy` | `linear` |
| `--fault-tolerance-config` | `FaultToleranceConfig(engine_recovery_timeout_sec=120` |
| `--master-addr` | `127.0.0.1` |
| `--master-port` | `29501` |
| `--max-parallel-loading-workers` | `None` |
| `--nnodes` | `1` |
| `--node-rank` | `0` |
| `--numa-bind` | `False` |
| `--numa-bind-cpus` | `None` |
| `--numa-bind-nodes` | `None` |
| `--pipeline-parallel-size` | `1` |
| `--prefill-context-parallel-size` | `1` |
| `--ray-workers-use-nsight` | `False` |
| `--tensor-parallel-size` | `1` |
| `--ubatch-size` | `0` |
| `--worker-cls` | `auto` |
| `--worker-extension-cls` | `` |

### CacheConfig (21)

| flag | default |
|---|---|
| `--block-size` | `None` |
| `--enable-mamba-shared-prefix-checkpoint` | `False` |
| `--enable-prefix-caching` | `None` |
| `--gpu-memory-utilization` | `0.92` |
| `--kv-cache-dtype` | `auto` |
| `--kv-cache-dtype-skip-layers` | `[]` |
| `--kv-cache-memory-bytes` | `None` |
| `--kv-offloading-backend` | `native` |
| `--kv-offloading-size` | `None` |
| `--kv-sharing-fast-prefill` | `False` |
| `--mamba-block-size` | `None` |
| `--mamba-cache-dtype` | `auto` |
| `--mamba-cache-mode` | `None` |
| `--mamba-ssm-cache-dtype` | `auto` |
| `--num-gpu-blocks-override` | `None` |
| `--prefix-cache-retention-interval` | `0` |
| `--prefix-caching-hash-algo` | `sha256` |
| `--prefix-match-unit` | `None` |
| `--replayssm-buffer-len` | `16` |
| `--swa-bounded-replay` | `True` |
| `--use-replayssm` | `False` |

### OffloadConfig (7)

| flag | default |
|---|---|
| `--cpu-offload-gb` | `0` |
| `--cpu-offload-params` | `set(` |
| `--offload-backend` | `auto` |
| `--offload-group-size` | `0` |
| `--offload-num-in-group` | `1` |
| `--offload-params` | `set(` |
| `--offload-prefetch-step` | `1` |

### MultiModalConfig (24)

| flag | default |
|---|---|
| `--enable-mm-embeds` | `False` |
| `--interleave-mm-strings` | `False` |
| `--language-model-only` | `False` |
| `--limit-mm-per-prompt` | `{}` |
| `--media-io-kwargs` | `{}` |
| `--mm-device-do-normalize` | `None` |
| `--mm-encoder-attn-backend` | `None` |
| `--mm-encoder-attn-dtype` | `None` |
| `--mm-encoder-fp8-scale-path` | `None` |
| `--mm-encoder-fp8-scale-save-margin` | `1.5` |
| `--mm-encoder-fp8-scale-save-path` | `None` |
| `--mm-encoder-only` | `False` |
| `--mm-encoder-tp-mode` | `weights` |
| `--mm-hasher-algorithm` | `blake3` |
| `--mm-ipc-gpu-memory-gb` | `0` |
| `--mm-processor-cache-gb` | `4` |
| `--mm-processor-cache-type` | `lru` |
| `--mm-processor-device` | `auto` |
| `--mm-processor-kwargs` | `None` |
| `--mm-shm-cache-max-object-size-mb` | `128` |
| `--mm-tensor-ipc` | `direct_rpc` |
| `--skip-mm-profiling` | `False` |
| `--video-pruning-method` | `evs` |
| `--video-pruning-rate` | `None` |

### LoRAConfig (13)

| flag | default |
|---|---|
| `--default-mm-loras` | `None` |
| `--enable-lora` | `None` |
| `--enable-mixed-moe-lora-format` | `False` |
| `--enable-moe-shared-loras` | `False` |
| `--enable-tower-connector-lora` | `False` |
| `--fully-sharded-loras` | `False` |
| `--lora-dtype` | `auto` |
| `--lora-target-modules` | `None` |
| `--max-cpu-loras` | `None` |
| `--max-lora-cls-labels` | `None` |
| `--max-lora-rank` | `16` |
| `--max-loras` | `1` |
| `--specialize-active-lora` | `False` |

### LoggingConfig (3)

| flag | default |
|---|---|
| `--log-config-file` | `None` |
| `--log-level` | `None` |
| `--logging-config` | `None` |

### ObservabilityConfig (13)

| flag | default |
|---|---|
| `--collect-detailed-traces` | `None` |
| `--cudagraph-metrics` | `False` |
| `--custom-histogram-buckets` | `None` |
| `--enable-layerwise-nvtx-tracing` | `False` |
| `--enable-logging-iteration-details` | `False` |
| `--enable-mfu-metrics` | `False` |
| `--jit-monitor-mode` | `warn` |
| `--jit-monitor-verbose` | `False` |
| `--kv-cache-metrics` | `False` |
| `--kv-cache-metrics-sample` | `0.01` |
| `--otlp-traces-endpoint` | `None` |
| `--per-request-spec-decode-metrics` | `none` |
| `--show-hidden-metrics-for-version` | `None` |

### SchedulerConfig (18)

| flag | default |
|---|---|
| `--async-scheduling` | `None` |
| `--disable-chunked-mm-input` | `False` |
| `--disable-hybrid-kv-cache-manager` | `None` |
| `--enable-chunked-prefill` | `None` |
| `--long-prefill-token-threshold` | `0` |
| `--long-prefill-token-threshold-adaptive` | `False` |
| `--max-num-active-seqs` | `None` |
| `--max-num-batched-tokens` | `None` |
| `--max-num-queued-reqs` | `None` |
| `--max-num-queued-tokens` | `None` |
| `--max-num-scheduled-tokens` | `None` |
| `--max-num-seqs` | `None` |
| `--prefill-schedule-interval` | `1` |
| `--scheduler-cls` | `None` |
| `--scheduler-reserve-full-isl` | `True` |
| `--scheduling-policy` | `fcfs` |
| `--stream-interval` | `1` |
| `--watermark` | `0.0` |

### CompilationConfig (2)

| flag | default |
|---|---|
| `--cudagraph-capture-sizes` | `None` |
| `--max-cudagraph-capture-size` | `None` |

### KernelConfig (6)

| flag | default |
|---|---|
| `--enable-flashinfer-autotune` | `None` |
| `--ir-op-priority` | `IrOpPriorityConfig(rms_norm=[], fused_add_rms_norm=[], gelu_and_mul_sparse=[]` |
| `--linear-backend` | `auto` |
| `--moe-backend` | `auto` |
| `--monokernel` | `False` |
| `--sparse-indexer-topk-backend` | `auto` |

### VllmConfig (23)

| flag | default |
|---|---|
| `--additional-config` | `{}` |
| `--attention-config` | `AttentionConfig(backend=None, minimax_m3_msa_decode_backend='triton', backend_per_kind={}, flash_attn_version=None, flash_attn_max_num_splits_for_cuda_graph=32, tokenspeed_mla_min_split_kv=1, tq_max_kv_splits_for_cuda_graph=32, use_trtllm_attention=None, disable_flashinfer_q_quantization=False, mla_prefill_backend=None, use_prefill_query_quantization=False, trtllm_ragged_backend='trtllm-gen', indexer_kv_dtype='auto', indexer_sparse_logits=False, indexer_tp_shard_min_rows=65536, minimax_m3_indexer_cp=False, hisparse_config=None, use_non_causal=False, sparse_mla_force_mqa=False, sparse_mla_prefill_workspace_factor=None, flex_attn_block_m=None, flex_attn_block_n=None, flex_attn_q_block_size=None, flex_attn_kv_block_size=None` |
| `--aux-output-config` | `AuxOutputConfig(enable_return_routed_experts=False, max_bytes=None` |
| `--compilation-config` | `{'mode': None, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': [], 'ir_enable_torch_wrap': None, 'splitting_ops': None, 'compile_mm_encoder': False, 'cudagraph_mm_encoder': False, 'encoder_cudagraph_token_budgets': [], 'encoder_cudagraph_max_vision_items_per_batch': 0, 'encoder_cudagraph_max_frames_per_batch': None, 'cudagraph_decoder_replay': True, 'decoder_replay_cudagraph_capture_sizes': [], 'decoder_replay_trim_threshold': 768, 'compile_sizes': None, 'compile_ranges_endpoints': None, 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': None, 'cudagraph_num_of_warmups': 0, 'cudagraph_capture_sizes': None, 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': None, 'pass_config': {}, 'max_cudagraph_capture_size': None, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': False}, 'local_cache_dir': None, 'fast_moe_cold_start': None, 'static_all_moe_layers': []}` |
| `--diffusion-config` | `None` |
| `--ec-manager-config` | `EncoderCacheManagerConf ig(encoder_cache_manager_cls=None, manager_config={}` |
| `--ec-transfer-config` | `None` |
| `--engram-config` | `None` |
| `--kernel-config` | `KernelConfig(ir_op_prio rity=IrOpPriorityConfig(rms_norm=[], fused_add_rms_norm=[], gelu_and_mul_sparse=[]` |
| `--kv-events-config` | `None` |
| `--kv-transfer-config` | `None` |
| `--optimization-level` | `2` |
| `--performance-mode` | `balanced` |
| `--profiler-config` | `ProfilerConfig(profiler=None, torch_profiler_dir='', torch_profiler_activities=None, proton_profiler_dir='', proton_context='shadow', proton_data='tree', proton_backend=None, proton_mode=None, proton_hook=None, proton_output_format=None, proton_graph_attribution=False, torch_profiler_with_stack=True, torch_profiler_with_flops=False, torch_profiler_use_gzip=True, torch_profiler_dump_cuda_time_total=True, torch_profiler_record_shapes=False, torch_profiler_with_memory=False, capture_torch_profiler=False, detailed_trace_annotation=False, ignore_frontend=False, delay_iterations=0, max_iterations=0, warmup_iterations=0, active_iterations=5, wait_iterations=0` |
| `--reasoning-config` | `None` |
| `--spec-method` | `None` |
| `--spec-model` | `None` |
| `--spec-tokens` | `None` |
| `--speculative-config` | `None` |
| `--structured-outputs-config` | `StructuredOutputsConfig(backend='auto', disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False` |
| `--watchdog-config` | `WatchdogConfig(timeout=300, check_interval=10, dump_dir=''` |
| `--watermark-config` | `None` |
| `--weight-transfer-config` | `None` |

