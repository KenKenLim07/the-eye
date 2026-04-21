# Results and Discussion

This chapter reports the key findings produced by PH VibeCheck AI within the fixed observation window (March 25, 2026 to March 31, 2026; PH local time, Asia/Manila). Results are presented in two layers:
1. **Sentiment engine benchmarks** (to validate the hybrid approach in a Philippine news setting), and
2. **Dashboard-level analytics** (to interpret sentiment distributions, cross-source alignment, and entity-level patterns).

Unless stated otherwise, sentiment scores and labels refer to outputs of the deployed sentiment engine described in Chapters 3–4.

## Benchmark Evaluation of the Sentiment Engine (Reported Snapshot)

This section summarizes benchmark results produced by the evaluation scripts and benchmark assets described in Chapter 4 (see Appendix A for reproducibility commands). Where relevant, results are reported exactly as stored in the generated benchmark reports under `backend/reports/`.

### Manual Benchmark on Real News Articles (Primary, 3-Class)

Table 1: Manual benchmark results on a stratified real-news sample (3-class: Pos, Neu, Neg) for the observation window (March 25–31, 2026). The benchmark contains $n=200$ labeled articles, but $n=178$ were used after excluding clearly noisy/broken rows during conservative text cleaning. Inter-annotator agreement on the full labeled set is Cohen’s $\kappa=0.574$ ($n=200$).

| Model | Accuracy | Macro-F1 | F1 (Pos) | F1 (Neu) | F1 (Neg) |
|---|---:|---:|---:|---:|---:|
| VADER + PH patch | 0.573 | 0.524 | 0.678 | 0.289 | 0.604 |
| DistilBERT (SST-2)\* | 0.556 | 0.454 | 0.573 | 0.162 | 0.625 |
| Hybrid router | 0.545 | 0.467 | 0.585 | 0.208 | 0.609 |

\* Utilizes confidence-based neutralization (`DISTILBERT_NEUTRAL_MIN_CONF = 0.60`).

In this benchmark run, the hybrid router routed 136/178 articles to the DistilBERT path and 42/178 to the VADER path, reflecting the English-heavy nature of much of the sampled window. Route-level accuracy in the report is 0.537 for the DistilBERT route and 0.571 for the VADER route, indicating that routing quality and neutral handling both materially affect end-to-end performance.

### Manual Benchmark (Binary Subset)

Table 2: Binary benchmark results excluding neutral ground-truth (positive vs. negative only). This view helps interpret the effect of “abstention to neutral” when the true label is non-neutral.

| Model | Accuracy | Macro-F1 | Neutral-pred rate |
|---|---:|---:|---:|
| VADER + PH patch | 0.628 | 0.693 | 0.221 |
| DistilBERT (SST-2) | 0.662 | 0.661 | 0.007 |
| Hybrid router | 0.634 | 0.656 | 0.069 |

### Interpretation: Neutral Handling in News

Across all models, “neutral” remains the hardest class in news-style text because factual reporting and mixed-valence framing are common. Neutral predictions from the transformer pathway are introduced indirectly via abstention rules (confidence thresholds), while the rule-based VADER pathway supports an explicit neutral band (`VADER_NEUTRAL_BAND`). The hybrid router combines these behaviors across language regimes (Taglish-heavy → VADER+PH; English-heavy → DistilBERT), but overall performance still depends heavily on the composition of the sampled window and the neutralization thresholds used.

### Supplementary: Gold Sets (Sanity Checks for Tuning)

In addition to the manual benchmark, the project maintains two offline gold sets (Chapter 4 and Appendix B) used primarily for tuning and regression checks:
- a Tagalog/Taglish 3-class gold set for validating the PH VADER patch, and
- an English-only binary gold set for documenting the DistilBERT SST-2 baseline.

Because gold set outcomes can change when thresholds are adjusted (e.g., widening the VADER neutral band), the thesis treats these results as *supporting evidence* rather than as the main end-to-end claim. The recommended workflow is to populate the corresponding tables directly from `evaluate_vader_ph_gold.py` output before final printing (Appendix A).

## Overall Distribution and Temporal Trends (Dashboard Snapshot)

The dashboard layer summarizes sentiment as time-series signals (daily/rolling aggregates) and distribution snapshots per source. In a news domain, it is common for negative-labeled content to dominate due to frequent reporting on crime, disasters, and governance disputes; therefore, distribution plots are interpreted as *descriptive snapshots* rather than as direct evidence of outlet bias.

Figure placeholders for the hardbound thesis:
- A 7-day sentiment trends chart for the fixed observation window.
- An optional 30-day trends chart for exploratory monitoring (clearly labeled as supplementary).

![Sentiment trends over the last 7 days (March 25–31, 2026): negative (red), neutral (gray), positive (green).](figures/weekly-sentiment-trends.png){#fig:trends-7d}

## Pearson Correlation Matrix (Cross-Source Sentiment Alignment, Dashboard Snapshot)

To quantify whether outlet-level sentiment trends move together over time, Pearson correlation coefficients were computed using daily average sentiment scores per source.

$$
r_{XY}=\frac{\sum_{i=1}^{n}(x_i-\bar{x})(y_i-\bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i-\bar{x})^2}\sqrt{\sum_{i=1}^{n}(y_i-\bar{y})^2}}
$$

![Cross-source sentiment correlation heatmap (Pearson $r$) based on daily average sentiment scores (March 25–31, 2026).](figures/source-correlation-heatmap.png){#fig:correlation-heatmap}

Interpretation highlights from the reported snapshot include:
- Strong positive correlations indicate synchronized sentiment fluctuations that may reflect shared high-salience national events or similar topic selection.
- Strong negative correlations indicate opposing sentiment movement across the same time window (e.g., one outlet trending more negative while another trends more positive).

Important caveat: correlation quantifies statistical association only and does not imply causation or editorial coordination. In addition, sentiment estimates are produced by an automated pipeline and remain sensitive to news-domain ambiguity, sarcasm, and context-dependent meaning.

For thesis reporting, correlation values should be presented directly from a reproducible snapshot export (e.g., `backend/scripts/correlation_snapshot.py`), then interpreted as *signal alignment* rather than as evidence of editorial influence.

## Most Frequent Entities and Their Sentiment Profiles

Named Entity Recognition (NER) is applied to extract PERSON, ORG, and GPE entities [@nadeau2007ner]. Entities are ranked by mention frequency and paired with the average sentiment of the articles in which they appear.

If you include the entity chart in the hardbound thesis, it should present (a) top entities by mentions and (b) average sentiment associated with their coverage. This visualization is intended to support exploration and prioritization rather than definitive judgments about individuals or institutions.

### Qualitative review protocol (recommended for thesis defensibility)

To avoid overinterpreting entity-level sentiment averages, a lightweight qualitative check is recommended:
1. Select the top $N$ entities by mention frequency (e.g., $N=10$ to $20$).
2. For each entity, sample $K$ articles (e.g., $K=5$ to $10$) spanning multiple sources and multiple days.
3. Assign each sampled article to a coarse event category (crime, disaster, governance/legal, economy, international, etc.).
4. Summarize which categories dominate the entity’s mentions and how those categories plausibly drive the observed polarity.
5. Use the qualitative summary to contextualize the aggregate chart and to frame conclusions as patterns in coverage rather than judgments about an entity.
