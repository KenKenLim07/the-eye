# Conclusion and Recommendations

## Conclusion

This thesis designed and implemented **PH VibeCheck AI**, an end-to-end system for continuous monitoring of Philippine online news. The platform integrates scheduled web scraping, text normalization, hybrid sentiment analysis, and named entity extraction, and presents outputs through an interactive web interface that supports exploration of trends, cross-source comparisons, and navigation from aggregate views to individual articles for qualitative verification.

The primary technical contribution is a **hybrid sentiment engine** that combines (1) a Tagalog/Taglish-extended VADER pathway and (2) a lightweight DistilBERT SST-2 transformer pathway, routed per article using a language-signal heuristic. The benchmark results in Chapter 5 highlight the trade-offs that motivate this design: the Taglish-patched VADER pathway provides a strong, interpretable baseline for mixed-language inputs, while the transformer pathway offers efficient polarity scoring for English-heavy content under bounded CPU inference (truncation and offline caching). In the reported manual benchmark snapshot, VADER+PH achieved the highest three-class accuracy, while the hybrid router provided comparable performance with explicit routing metadata that supports auditing and future improvements.

More broadly, the system demonstrates that an operational pipeline—scheduled ingestion, reproducible storage, and transparent model metadata—can support scalable monitoring of large-scale news streams without replacing human interpretation. In this framing, NLP outputs function as signals that guide deeper reading rather than as definitive judgments about intent or bias.

## Limitations

Several limitations remain:
- **Domain mismatch and ambiguity:** news sentiment is inherently ambiguous; binary transformer baselines trained on general sentiment may misinterpret factual reporting and news framing.
- **Incomplete local lexicon coverage:** the Tagalog/Taglish lexicon patch improves coverage but cannot fully capture evolving slang, sarcasm, or context-dependent meanings.
- **Heuristic routing:** the hybrid router relies on language-signal heuristics and may misroute heavily mixed-language content or content in languages beyond English/Tagalog (e.g., Cebuano).
- **Correlation interpretability:** correlation measures statistical association in sentiment trends and does not imply causation or editorial coordination; missing data and uneven coverage can affect correlation estimates.

## Recommendations

Recommendations that follow directly from the implemented system include:
1. **Multilingual transformer upgrade:** Replace the English-first SST-2 baseline with a multilingual model better suited to Philippine code-switching, and evaluate with an explicit neutral objective.
2. **Expanded and versioned PH lexicon:** Continue expanding the Tagalog/Taglish lexicon patch while maintaining strict versioning so changes remain measurable and auditable.
3. **Larger gold-standard dataset:** Scale manual labeling beyond the current benchmark size to improve reliability of precision/recall estimates and enable stronger comparative evaluation.
4. **Improved entity analysis:** Add entity disambiguation and PH-specific NER improvements to reduce false merges/splits in entity aggregation.
5. **Automated data-quality monitoring:** Add observability checks for scraper health (silent failures, boilerplate repetition, missing timestamps) to improve reliability of downstream analytics.
6. **Richer temporal queries:** Extend dashboard filtering and aggregation to support flexible date ranges and event-based comparisons beyond fixed snapshot windows.
