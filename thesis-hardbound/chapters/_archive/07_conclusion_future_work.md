# Conclusion and Future Work

## Conclusion

This thesis designed and implemented **PH VibeCheck AI**, an end-to-end system for continuous monitoring of Philippine online news. The platform integrates scheduled web scraping, text normalization, hybrid sentiment analysis, and named entity extraction, and presents results through an interactive web interface that supports exploration of trends, cross-source comparisons, and navigation from aggregate views to individual articles for qualitative verification.

The primary technical contribution is a **hybrid sentiment engine** that combines (1) a Tagalog/Taglish-extended VADER pathway and (2) a lightweight DistilBERT SST-2 transformer pathway, routed per article using a language-signal heuristic. The evaluation results summarized in Chapter 5 show that this hybrid design improves robustness in a multilingual, code-switched news setting—especially in handling borderline and factual reporting text where “neutral” is otherwise difficult to model reliably.

In addition, the system demonstrates how operational pipeline design choices (e.g., scheduled ingestion, consistent storage, and model metadata logging) support reproducible analytics. The dashboards and cached public sentiment outputs make it practical to monitor large-scale news streams without relying exclusively on manual review, while still encouraging human interpretation rather than automated claims of intent or bias.

## Limitations

Several limitations remain:
- **Domain mismatch and ambiguity:** News sentiment is inherently ambiguous. The transformer baseline (SST-2) is trained on general sentiment rather than a news-specific neutral objective, and may misinterpret news framing or factual statements.
- **Incomplete local lexicon coverage:** The Tagalog/Taglish lexicon patch improves local coverage but cannot fully capture evolving slang, context-dependent polarity shifts, or subtle discourse cues (e.g., sarcasm).
- **Heuristic routing:** The hybrid router is based on language-signal heuristics and may misroute heavily mixed-language content, or content in languages beyond English/Tagalog (e.g., Cebuano).
- **Correlation interpretability:** Outlet correlation measures statistical association in sentiment trends and does not imply causation, coordination, or editorial influence; missing data and uneven coverage can also affect correlations.

## Future Work and Recommendations

Future improvements that follow directly from the implemented system include:
1. **Multilingual transformer upgrade:** Replace the English-first SST-2 baseline with a multilingual model better suited to code-switched Philippine text, and evaluate with an explicit neutral objective.
2. **Expanded and versioned PH lexicon:** Continue expanding the Tagalog/Taglish lexicon patch with more coverage of slang, political jargon, and domain-specific terms, while maintaining strict versioning so changes are measurable and thesis-defensible.
3. **Larger gold-standard dataset:** Scale the manually labeled dataset beyond the current benchmark size, enabling more reliable estimates of precision/recall and supporting statistically stronger comparisons across model variants.
4. **Improved entity analysis:** Add entity disambiguation and PH-specific NER improvements to reduce false merges/splits in entity aggregation.
5. **Automated data-quality monitoring:** Add observability checks for scraper health (e.g., silent failures, repeated boilerplate, missing timestamps) to improve the reliability of downstream analytics.
6. **Richer temporal queries:** Extend dashboard filtering and aggregation to support flexible date ranges and event-based comparisons beyond fixed snapshot windows.

Overall, PH VibeCheck AI provides a practical foundation for scalable, transparent news monitoring in the Philippine context. With targeted improvements in multilingual modeling, labeled data, and operational monitoring, the system can support stronger research in computational journalism and media analytics.
