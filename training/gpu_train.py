"""Fine-tune Gemma 4 E2B (LoRA) on FinSL sign names and predict the test sample, on any CUDA machine (Verda, Modal).

  python gpu_train.py train --data ~/finsl-data --out ~/finsl-gemma4-e2b --limit 64 --max-steps 5   # smoke test
  python gpu_train.py train --data ~/finsl-data --out ~/finsl-gemma4-e2b                              # full run
  python gpu_train.py predict --data ~/finsl-data --adapter ~/finsl-gemma4-e2b --out finetuned_e2b.jsonl
  python gpu_train.py predict --data ~/finsl-data --out base_e2b.jsonl                                 # untrained
"""
import argparse
import json
import time
from pathlib import Path

import os

MODEL_ID = os.environ.get("FINSL_MODEL", "google/gemma-4-E2B-it")  # or google/gemma-4-E4B-it; Apache 2.0, not gated

LORA = dict(r=16, lora_alpha=32, lora_dropout=0.05,
            target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)")
LR, BATCH, ACCUM, MAX_LEN = 2e-4, 8, 2, 256  # effective batch 16
EPOCHS = int(os.environ.get("FINSL_EPOCHS", "3"))


def _load(adapter_dir: str | None):
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    if adapter_dir:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter_dir)
    model.eval()
    return tok, model


def _prompt_text(tok, prompt: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False,
                                   add_generation_prompt=True, enable_thinking=False)


def _encode(tok, ex: dict) -> dict:
    """Token ids for prompt + answer; loss only on the answer and the end-of-turn."""
    prefix = _prompt_text(tok, ex["prompt"])
    full = tok.apply_chat_template([{"role": "user", "content": ex["prompt"]},
                                    {"role": "assistant", "content": ex["answer"]}],
                                   tokenize=False, enable_thinking=False)
    if not full.startswith(prefix):
        full = prefix + ex["answer"] + (tok.eos_token or "")
    p_ids = tok(prefix, add_special_tokens=False)["input_ids"]
    f_ids = tok(full, add_special_tokens=False)["input_ids"][:MAX_LEN]
    labels = [-100] * min(len(p_ids), len(f_ids)) + f_ids[len(p_ids):]
    return {"input_ids": f_ids, "labels": labels}


def _batches(items: list[dict], size: int, pad_id: int):
    import torch

    for i in range(0, len(items), size):
        chunk = items[i : i + size]
        n = max(len(x["input_ids"]) for x in chunk)
        ids = torch.full((len(chunk), n), pad_id)
        labels = torch.full((len(chunk), n), -100)
        mask = torch.zeros((len(chunk), n), dtype=torch.long)
        for j, x in enumerate(chunk):
            ids[j, : len(x["input_ids"])] = torch.tensor(x["input_ids"])
            labels[j, : len(x["labels"])] = torch.tensor(x["labels"])
            mask[j, : len(x["input_ids"])] = 1
        yield ids.cuda(), labels.cuda(), mask.cuda()


def train(data: Path, adapter_dir: str, limit: int | None = None, max_steps: int | None = None) -> dict:
    import random

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import get_cosine_schedule_with_warmup

    from finsl.testset import rows_for
    from finsl.train_data import example

    started = time.time()
    tok, model = _load(None)
    model.train()
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(task_type="CAUSAL_LM", **LORA))
    model.print_trainable_parameters()
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0

    train_rows, val_rows = rows_for("train", data), rows_for("val", data)
    random.Random(0).shuffle(train_rows)
    train_rows = train_rows[:limit]
    val_rows = val_rows[: max(limit or 0, 200)]
    train_ex = [_encode(tok, example(r)) for r in train_rows]
    val_ex = [_encode(tok, example(r)) for r in val_rows]
    print(f"train {len(train_ex)} rows, val {len(val_ex)} rows")

    steps = max_steps or (len(train_ex) // (BATCH * ACCUM)) * EPOCHS
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR, weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(opt, int(0.05 * steps), steps)

    def val_loss() -> float:
        model.eval()
        total, n = 0.0, 0
        with torch.no_grad():
            for ids, labels, mask in _batches(val_ex, BATCH, pad):
                total += model(input_ids=ids, attention_mask=mask, labels=labels).loss.item()
                n += 1
        model.train()
        return total / max(n, 1)

    log = {"model": MODEL_ID, "gpu": __import__("torch").cuda.get_device_name(0), "train_rows": len(train_ex), "val_rows": len(val_ex),
           "lora": {k: v for k, v in LORA.items() if k != "target_modules"}, "lr": LR, "effective_batch": BATCH * ACCUM,
           "val_loss": [("step 0", round(val_loss(), 4))]}
    print("val loss before training:", log["val_loss"][0])
    step, micro = 0, 0
    epoch = 0
    while step < steps:
        epoch += 1
        random.Random(epoch).shuffle(train_ex)
        # similar lengths together = less padding
        ordered = sorted(train_ex, key=lambda x: len(x["input_ids"]))
        chunks = [ordered[i : i + BATCH] for i in range(0, len(ordered), BATCH)]
        random.Random(epoch).shuffle(chunks)
        for chunk in chunks:
            ids, labels, mask = next(_batches(chunk, BATCH, pad))
            loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss / ACCUM
            loss.backward()
            micro += 1
            if micro % ACCUM:
                continue
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(), sched.step(), opt.zero_grad()
            step += 1
            if step % 20 == 0 or step == steps:
                print(f"step {step}/{steps} loss {loss.item() * ACCUM:.4f} ({time.time() - started:.0f}s)", flush=True)
            if step >= steps:
                break
        log["val_loss"].append((f"epoch {epoch}", round(val_loss(), 4)))
        print("val loss:", log["val_loss"][-1], flush=True)

    model.save_pretrained(adapter_dir)
    log["minutes"] = round((time.time() - started) / 60, 1)
    log["steps"] = step
    Path(adapter_dir, "train_log.json").write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))
    return log


def _generate(tok, model, texts: list[tuple[str, str]], max_new_tokens: int = 48) -> list[str]:
    import torch

    from finsl.prompt import build_prompt

    tok.padding_side = "left"
    prompts = [_prompt_text(tok, build_prompt(t, lang)) for t, lang in texts]
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False)
    return tok.batch_decode(out[:, enc["input_ids"].shape[1] :], skip_special_tokens=True)


def predict(data: Path, adapter_dir: str | None) -> list[dict]:
    from finsl.prompt import parse_signs
    from finsl.testset import eval_sample

    tok, model = _load(adapter_dir)
    rows = eval_sample(data)
    results = []
    for i in range(0, len(rows), 16):
        chunk = rows[i : i + 16]
        started = time.time()
        answers = _generate(tok, model, [(r["text"], r["lang"]) for r in chunk])
        per_row = (time.time() - started) / len(chunk)
        for r, a in zip(chunk, answers):
            results.append({"text": r["text"], "lang": r["lang"], "source": r["source"], "signs_ref": r["signs"],
                            "signs_pred": parse_signs(a), "raw": a[:300], "seconds": round(per_row, 2)})
    # one sentence alone, as the live endpoint sees it
    started = time.time()
    _generate(tok, model, [("Juna Helsinkiin lähtee laiturilta neljä.", "fi")])
    print(f"single sentence: {time.time() - started:.2f}s")
    return results

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["train", "predict"])
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--adapter")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-steps", type=int)
    a = ap.parse_args()
    if a.command == "train":
        train(a.data, a.out, a.limit, a.max_steps)
    else:
        rows = predict(a.data, a.adapter)
        Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} rows to {a.out}")


if __name__ == "__main__":
    main()
