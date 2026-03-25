# CultureDx: 18-Condition Sweep Results (N=200 per condition)

## Table 1: Parent-Normalized Metrics

| Mode | Evidence | LingxiDiag-16k Top-1 Acc | LingxiDiag-16k Top-3 Acc | LingxiDiag-16k Macro F1 | MDD-5k Top-1 Acc | MDD-5k Top-3 Acc | MDD-5k Macro F1 | |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | |
| Single-Agent | None | 40.5 | 52.5 | 7.8 | **52.5** | **76.5** | **13.0** | |
| Single-Agent | BGE-M3 | 40.5 | 73.0 | 7.8 | 47.0 | 62.5 | 6.3 | |
| Single-Agent | BGE-M3 (no somat.) | 39.5 | 72.5 | 7.6 | 47.0 | 62.5 | 6.3 | |
| HiED (Hierarchical) | None | 41.0 | 63.0 | 9.3 | 52.0 | 71.5 | 6.4 | |
| HiED (Hierarchical) | BGE-M3 | **45.0** | **74.0** | **10.3** | 46.0 | 61.5 | 5.4 | |
| HiED (Hierarchical) | BGE-M3 (no somat.) | 41.5 | **74.0** | 8.6 | 45.0 | 62.0 | 5.3 | |
| PsyCoT (Chain-of-Thought) | None | 41.5 | 62.5 | 9.6 | 51.0 | 67.0 | 7.5 | |
| PsyCoT (Chain-of-Thought) | BGE-M3 | 41.5 | **74.0** | 8.4 | 45.0 | 60.0 | 5.8 | |
| PsyCoT (Chain-of-Thought) | BGE-M3 (no somat.) | 41.0 | **74.0** | 8.3 | 47.5 | 60.5 | 6.5 | |

## Table 2: Exact-Match Metrics

| Mode | Evidence | LingxiDiag-16k Top-1 Acc (exact) | LingxiDiag-16k Top-3 Acc (exact) | LingxiDiag-16k Macro F1 (exact) | MDD-5k Top-1 Acc (exact) | MDD-5k Top-3 Acc (exact) | MDD-5k Macro F1 (exact) | |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | |
| Single-Agent | None | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | |
| Single-Agent | BGE-M3 | **36.0** | 36.0 | 4.7 | 5.0 | 5.0 | 0.5 | |
| Single-Agent | BGE-M3 (no somat.) | 35.5 | 35.5 | 4.8 | 4.5 | 4.5 | 0.5 | |
| HiED (Hierarchical) | None | 29.0 | 34.0 | 5.3 | **40.5** | **43.5** | 4.1 | |
| HiED (Hierarchical) | BGE-M3 | 30.5 | **39.0** | 5.9 | 28.5 | 29.5 | 3.3 | |
| HiED (Hierarchical) | BGE-M3 (no somat.) | 32.0 | **39.0** | 5.6 | 27.5 | 29.0 | 3.1 | |
| PsyCoT (Chain-of-Thought) | None | 32.5 | 34.0 | **6.4** | 32.0 | 39.0 | **4.8** | |
| PsyCoT (Chain-of-Thought) | BGE-M3 | 32.5 | **39.0** | 5.6 | 23.5 | 28.0 | 3.5 | |
| PsyCoT (Chain-of-Thought) | BGE-M3 (no somat.) | 32.5 | **39.0** | 5.6 | 25.0 | 27.5 | 4.1 | |

## Table 3: Combined Results (Paper-Ready)

Metrics are reported as percentages. Best result per column in **bold**.

| Mode | Evidence | LingxiDiag-16k: Top-1 Acc | LingxiDiag-16k: Top-3 Acc | LingxiDiag-16k: Macro F1 | LingxiDiag-16k: Top-1 Acc (exact) | LingxiDiag-16k: Top-3 Acc (exact) | LingxiDiag-16k: Macro F1 (exact) | MDD-5k: Top-1 Acc | MDD-5k: Top-3 Acc | MDD-5k: Macro F1 | MDD-5k: Top-1 Acc (exact) | MDD-5k: Top-3 Acc (exact) | MDD-5k: Macro F1 (exact) | |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | |
| Single-Agent | None | 40.5 | 52.5 | 7.8 | 0.0 | 0.0 | 0.0 | **52.5** | **76.5** | **13.0** | 0.0 | 0.0 | 0.0 | |
| Single-Agent | BGE-M3 | 40.5 | 73.0 | 7.8 | **36.0** | 36.0 | 4.7 | 47.0 | 62.5 | 6.3 | 5.0 | 5.0 | 0.5 | |
| Single-Agent | BGE-M3 (no somat.) | 39.5 | 72.5 | 7.6 | 35.5 | 35.5 | 4.8 | 47.0 | 62.5 | 6.3 | 4.5 | 4.5 | 0.5 | |
| HiED (Hierarchical) | None | 41.0 | 63.0 | 9.3 | 29.0 | 34.0 | 5.3 | 52.0 | 71.5 | 6.4 | **40.5** | **43.5** | 4.1 | |
| HiED (Hierarchical) | BGE-M3 | **45.0** | **74.0** | **10.3** | 30.5 | **39.0** | 5.9 | 46.0 | 61.5 | 5.4 | 28.5 | 29.5 | 3.3 | |
| HiED (Hierarchical) | BGE-M3 (no somat.) | 41.5 | **74.0** | 8.6 | 32.0 | **39.0** | 5.6 | 45.0 | 62.0 | 5.3 | 27.5 | 29.0 | 3.1 | |
| PsyCoT (Chain-of-Thought) | None | 41.5 | 62.5 | 9.6 | 32.5 | 34.0 | **6.4** | 51.0 | 67.0 | 7.5 | 32.0 | 39.0 | **4.8** | |
| PsyCoT (Chain-of-Thought) | BGE-M3 | 41.5 | **74.0** | 8.4 | 32.5 | **39.0** | 5.6 | 45.0 | 60.0 | 5.8 | 23.5 | 28.0 | 3.5 | |
| PsyCoT (Chain-of-Thought) | BGE-M3 (no somat.) | 41.0 | **74.0** | 8.3 | 32.5 | **39.0** | 5.6 | 47.5 | 60.5 | 6.5 | 25.0 | 27.5 | 4.1 | |

## Table 4: Runtime (seconds per case)

| Mode | Evidence | LingxiDiag-16k | MDD-5k |
| :--- | :--- | ---: | ---: |
| Single-Agent | None | 2.9 | 7.1 |
| Single-Agent | BGE-M3 | 14.3 | 30.0 |
| Single-Agent | BGE-M3 (no somat.) | 12.4 | 27.0 |
| HiED (Hierarchical) | None | 13.6 | 52.0 |
| HiED (Hierarchical) | BGE-M3 | 48.9 | 111.1 |
| HiED (Hierarchical) | BGE-M3 (no somat.) | 18.4 | 34.3 |
| PsyCoT (Chain-of-Thought) | None | 0.0 | 0.0 |
| PsyCoT (Chain-of-Thought) | BGE-M3 | 8.0 | 24.0 |
| PsyCoT (Chain-of-Thought) | BGE-M3 (no somat.) | 7.9 | 24.2 |

---

## LaTeX Version (Parent-Normalized)

```latex
\begin{table}[t]
\centering
\caption{CultureDx diagnostic performance across reasoning modes and evidence conditions (N=200). Metrics are parent-normalized. Best per column in \textbf{bold}.}
\label{tab:main_results}
\small
\begin{tabular}{llrrrrrr}
\toprule
 &  & \multicolumn{3}{c}{LingxiDiag\text{-}16k} & \multicolumn{3}{c}{MDD\text{-}5k} \\
\cmidrule(lr){3-5} \cmidrule(lr){6-8} 
Mode & Evidence & Top-1 Acc & Top-3 Acc & Macro F1 & Top-1 Acc & Top-3 Acc & Macro F1 \\
\midrule
Single-Agent & None & 40.5 & 52.5 & 7.8 & \textbf{52.5} & \textbf{76.5} & \textbf{13.0} \\
Single-Agent & BGE-M3 & 40.5 & 73.0 & 7.8 & 47.0 & 62.5 & 6.3 \\
Single-Agent & BGE-M3 (no somat.) & 39.5 & 72.5 & 7.6 & 47.0 & 62.5 & 6.3 \\
\addlinespace
HiED (Hierarchical) & None & 41.0 & 63.0 & 9.3 & 52.0 & 71.5 & 6.4 \\
HiED (Hierarchical) & BGE-M3 & \textbf{45.0} & \textbf{74.0} & \textbf{10.3} & 46.0 & 61.5 & 5.4 \\
HiED (Hierarchical) & BGE-M3 (no somat.) & 41.5 & \textbf{74.0} & 8.6 & 45.0 & 62.0 & 5.3 \\
\addlinespace
PsyCoT (Chain-of-Thought) & None & 41.5 & 62.5 & 9.6 & 51.0 & 67.0 & 7.5 \\
PsyCoT (Chain-of-Thought) & BGE-M3 & 41.5 & \textbf{74.0} & 8.4 & 45.0 & 60.0 & 5.8 \\
PsyCoT (Chain-of-Thought) & BGE-M3 (no somat.) & 41.0 & \textbf{74.0} & 8.3 & 47.5 & 60.5 & 6.5 \\
\bottomrule
\end{tabular}
\end{table}
```

## LaTeX Version (Exact-Match)

```latex
\begin{table}[t]
\centering
\caption{CultureDx exact-match diagnostic performance (N=200). Best per column in \textbf{bold}.}
\label{tab:exact_results}
\small
\begin{tabular}{llrrrrrr}
\toprule
 &  & \multicolumn{3}{c}{LingxiDiag\text{-}16k} & \multicolumn{3}{c}{MDD\text{-}5k} \\
\cmidrule(lr){3-5} \cmidrule(lr){6-8} 
Mode & Evidence & Top-1 Acc & Top-3 Acc & Macro F1 & Top-1 Acc & Top-3 Acc & Macro F1 \\
\midrule
Single-Agent & None & 0.0 & 0.0 & 0.0 & 0.0 & 0.0 & 0.0 \\
Single-Agent & BGE-M3 & \textbf{36.0} & 36.0 & 4.7 & 5.0 & 5.0 & 0.5 \\
Single-Agent & BGE-M3 (no somat.) & 35.5 & 35.5 & 4.8 & 4.5 & 4.5 & 0.5 \\
\addlinespace
HiED (Hierarchical) & None & 29.0 & 34.0 & 5.3 & \textbf{40.5} & \textbf{43.5} & 4.1 \\
HiED (Hierarchical) & BGE-M3 & 30.5 & \textbf{39.0} & 5.9 & 28.5 & 29.5 & 3.3 \\
HiED (Hierarchical) & BGE-M3 (no somat.) & 32.0 & \textbf{39.0} & 5.6 & 27.5 & 29.0 & 3.1 \\
\addlinespace
PsyCoT (Chain-of-Thought) & None & 32.5 & 34.0 & \textbf{6.4} & 32.0 & 39.0 & \textbf{4.8} \\
PsyCoT (Chain-of-Thought) & BGE-M3 & 32.5 & \textbf{39.0} & 5.6 & 23.5 & 28.0 & 3.5 \\
PsyCoT (Chain-of-Thought) & BGE-M3 (no somat.) & 32.5 & \textbf{39.0} & 5.6 & 25.0 & 27.5 & 4.1 \\
\bottomrule
\end{tabular}
\end{table}
```

## Key Findings

- **LingxiDiag-16k** best parent-normalized Top-1: 45.0% (HiED (Hierarchical), BGE-M3)
- **LingxiDiag-16k** best exact-match Top-1: 36.0% (Single-Agent, BGE-M3)
- **MDD-5k** best parent-normalized Top-1: 52.5% (Single-Agent, None)
- **MDD-5k** best exact-match Top-1: 40.5% (HiED (Hierarchical), None)

### Evidence Effect (averaged across modes)

- LingxiDiag-16k (Parent-Norm) Top-1 Acc: No Evidence=41.0%, BGE-M3=42.3%, No Somat.=40.7%
- LingxiDiag-16k (Exact) Top-1 Acc: No Evidence=20.5%, BGE-M3=33.0%, No Somat.=33.3%
- MDD-5k (Parent-Norm) Top-1 Acc: No Evidence=51.8%, BGE-M3=46.0%, No Somat.=46.5%
- MDD-5k (Exact) Top-1 Acc: No Evidence=24.2%, BGE-M3=19.0%, No Somat.=19.0%

### Mode Effect (averaged across evidence conditions)

- LingxiDiag-16k Single-Agent: Top-1=40.2%, Top-3=66.0%
- LingxiDiag-16k HiED (Hierarchical): Top-1=42.5%, Top-3=70.3%
- LingxiDiag-16k PsyCoT (Chain-of-Thought): Top-1=41.3%, Top-3=70.2%
- MDD-5k Single-Agent: Top-1=48.8%, Top-3=67.2%
- MDD-5k HiED (Hierarchical): Top-1=47.7%, Top-3=65.0%
- MDD-5k PsyCoT (Chain-of-Thought): Top-1=47.8%, Top-3=62.5%
