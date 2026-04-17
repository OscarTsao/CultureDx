# 8. Conclusion

CultureDx shows that Chinese psychiatric diagnosis benefits from a verify-first architecture rather than from more free-form generation alone. On the committed LingxiDiag-16K validation split, the best diagnose-then-verify configuration reaches 0.527 Overall, improving over the internal single-model baseline by 0.045 absolute and ranking first among the committed LLM baselines in the paper comparison table. The same pattern holds across the partial multi-backbone runs, where DtV improves Overall by +0.104 to +0.262.

The remaining gap is also clear. The comorbidity gate already behaves like a low-cost safety net, but Z71/Others handling remains weak and limits further improvement. The next version of CultureDx therefore should focus less on additional generic reasoning prompts and more on explicit handling of counseling/residual cases, open-set evaluation, and continued refinement of the culture-specific evidence layer.
