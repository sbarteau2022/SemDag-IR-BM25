"""LoRA SFT recipe for Gemma 4 E4B on this dataset (UNTESTED here: no GPU in the build env).

Run on a Kaggle GPU notebook (or any CUDA box) with transformers, peft, trl installed:
  python train_lora_recipe.py --model <path-or-id-of-gemma-4-e4b-it> --data <dir with train.jsonl/val.jsonl>

Notes
- Train on the bf16 instruct checkpoint, then load the adapter on the scored
  QAT checkpoint (gemma-4-e4b-it-qat-w4a16-ct). Check that target module names
  match between the two before submitting.
- Loss is on assistant turns only (thoughts + tool calls + final summary);
  tool observations, the system prompt and the issue are masked.
- Rank 64 keeps the adapter small; the competition limit we noted is rank <= 128.
- Re-render the data with the deployed system prompt first:
    python render.py <raw_dir> <out_dir> --system <submission>/prompts/system.md
"""
import argparse

from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoTokenizer
from trl import SFTConfig, SFTTrainer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="adapters/main_lora")
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--epochs", type=float, default=2)
    a = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(a.model)
    ds = load_dataset("json", data_files={"train": f"{a.data}/train.jsonl", "validation": f"{a.data}/val.jsonl"})
    ds = ds.remove_columns(["metadata", "id"])

    peft_cfg = LoraConfig(
        r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    cfg = SFTConfig(
        output_dir=a.out, num_train_epochs=a.epochs, per_device_train_batch_size=1,
        gradient_accumulation_steps=16, learning_rate=1e-4, lr_scheduler_type="cosine",
        warmup_ratio=0.03, bf16=True, gradient_checkpointing=True, logging_steps=10,
        eval_strategy="steps", eval_steps=100, save_strategy="steps", save_steps=200,
        max_length=12288, assistant_only_loss=True, report_to="none",
    )
    trainer = SFTTrainer(model=a.model, args=cfg, train_dataset=ds["train"],
                         eval_dataset=ds["validation"], processing_class=tok, peft_config=peft_cfg)
    trainer.train()
    trainer.save_model(a.out)  # writes adapter_config.json + adapter_model.safetensors


if __name__ == "__main__":
    main()
