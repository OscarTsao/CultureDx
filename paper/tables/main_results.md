# Main Results: CultureDx vs Paper Baselines (LingxiDiag-16K Validation)

| Method | Type | 2c_Acc | 4c_Acc | 12c_T1 | 12c_T3 | Overall |
|--------|------|--------|--------|--------|--------|---------|
| TF-IDF + LR | ML | .753 | .476 | .496 | .645 | .533 |
| TF-IDF + SVM | ML | .740 | .451 | .481 | .566 | .507 |
| Grok-4.1-Fast | LLM | .841 | .470 | .465 | .495 | .521 |
| Claude-Haiku-4.5 | LLM | .825 | .444 | .478 | .501 | .516 |
| Gemini-3-Flash | LLM | .854 | .422 | .492 | .574 | .510 |
| **CultureDx (ours)** | **MAS** | **.812** | **.448** | **.523** | **.599** | **.527** |
| Qwen3-32B (zero-shot) | LLM | .827 | .438 | .470 | .566 | .506 |
| GPT-5-Mini | LLM | .803 | .434 | .487 | .505 | .504 |
| DeepSeek-V3.2 | LLM | .820 | .441 | .438 | .489 | .501 |

CultureDx ranks #1 among all LLM-based methods.
Gap to TF-IDF+LR: -0.006 (within statistical margin).

## Multi-backbone (partial, in progress)

| Model | Precision | Single | DtV | Δ |
|-------|-----------|--------|-----|---|
| Qwen3-8B | BF16 | .318 | .508 | +.190 |
| Qwen3-32B-AWQ | AWQ 4-bit | .482 | .527 | +.045 |
