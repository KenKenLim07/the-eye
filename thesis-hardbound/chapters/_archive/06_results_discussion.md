# Results and Discussion

This chapter reports findings from the observation window and interprets the patterns surfaced by the dashboards. Sentiment scores and labels refer to outputs of the deployed sentiment engine (see `thesis-hardbound/SYSTEM_FACTS.md` for the verified implementation details).

## Overall Distribution and Temporal Trends

Across the 7-day observation window (2026-03-25 to 2026-03-31; $n=2{,}709$), negative sentiment dominates the dataset. In the reported snapshot, negative sentiment accounts for 57.6% of articles ($n=1{,}561$), compared to 38.3% positive ($n=1{,}038$) and 4.1% neutral ($n=110$). This skew is expected in a news domain where crime, disasters, and governance disputes are frequently covered, and it should not be interpreted as an inherent bias signal by itself.

![Sentiment trends over the last 7 days (2026-03-25 to 2026-03-31): negative (red), neutral (gray), positive (green).](figures/weekly-sentiment-trends.png){#fig:trends-7d}

### Supplementary View: Last 30 Days (Optional)

The dashboards also support longer windows (e.g., 30 days) for exploratory monitoring. In the ACM snapshot, the 30-day view is treated as supplementary because it can include noisier content categories and reflects uneven collection coverage while scrapers are being optimized. If included in the hardbound thesis, the key requirement is to clearly separate exploratory long-window summaries from primary claims based on the fixed 7-day snapshot.

## Pearson Correlation Matrix (Cross-Source Sentiment Alignment)

To quantify whether outlet-level sentiment trends move together over time, Pearson correlation coefficients were computed using **daily average sentiment scores** per source.

$$
r_{XY}=\frac{\sum_{i=1}^{n}(x_i-\bar{x})(y_i-\bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i-\bar{x})^2}\sqrt{\sum_{i=1}^{n}(y_i-\bar{y})^2}}
$$

Here, $x_i$ and $y_i$ denote the daily average sentiment scores for sources $X$ and $Y$ on day $i$. The coefficient ranges from $-1$ (inverse relationship) to $+1$ (strong positive relationship), while values near $0$ indicate weak linear association.

![Cross-source sentiment correlation heatmap (Pearson $r$) based on daily average sentiment scores (March 25–31, 2026).](figures/source-correlation-heatmap.png){#fig:correlation-heatmap}

Interpretation highlights from the reported snapshot include:
- Strong positive correlations indicate synchronized sentiment fluctuations that may reflect shared high-salience national events or similar topic selection.
- Strong negative correlations indicate opposing sentiment movement across the same time window (e.g., one outlet trending more negative while another trends more positive).

Important caveat: correlation quantifies **statistical association only** and does not imply causation or editorial coordination. In addition, sentiment estimates are produced by an automated hybrid pipeline and remain sensitive to news-domain ambiguity, sarcasm, and context-dependent meanings.

#### Example relationships (ACM snapshot; revalidate for final hardbound figures)

In the ACM snapshot, Manila Bulletin shows a strong positive correlation with Philstar ($r=0.657$) and ABS-CBN ($r=0.687$), suggesting synchronized sentiment movement over the aligned observation days. In contrast, a strong negative correlation is observed between GMA and Manila Bulletin ($r=-0.668$), indicating opposing sentiment trend movement during the same period. These examples are presented as *signal-level alignment* rather than evidence of causation.

If you include a per-outlet daily trend figure in the hardbound thesis, a useful narrative structure is:
- pick one strongly positive pair and one strongly negative pair,
- describe one observable divergence/convergence event across the week, and
- connect it back to the Pearson interpretation (without overclaiming editorial influence).

## Most Frequent Entities and Their Sentiment Profiles

Named Entity Recognition (NER) is applied to extract PERSON, ORG, and GPE entities (spaCy-based NER [@spacy; @nadeau2007ner]). Entities are ranked by mention frequency, and each entity is paired with the average sentiment of the articles in which it appears.

If you include the entity chart figure in the hardbound thesis, it should present: (a) top entities by mentions and (b) average sentiment associated with their coverage. This visualization is intended to support exploration and prioritization rather than definitive claims about individuals or institutions.

Example interpretation from the ACM snapshot (to be revalidated against the hardbound dataset window):
- Highly mentioned institutional/political entities tend to carry negative average sentiment during politically active weeks (e.g., legal proceedings, policy disputes, governance conflict).
- Geographic entities (e.g., “Manila”, “Philippines”) often remain near-neutral because they frequently act as contextual references rather than evaluative targets.

#### Qualitative review protocol (recommended for thesis defensibility)

To avoid overinterpreting entity-level sentiment averages, this thesis recommends a lightweight qualitative check:
1. Select the top $N$ entities by mention frequency (e.g., $N=10$ to $20$).
2. For each entity, sample $K$ articles (e.g., $K=5$ to $10$) spanning multiple sources and multiple days.
3. Assign each sampled article to a coarse event category (crime, disaster, governance/legal, economy, international, lifestyle, etc.).
4. Summarize which categories dominate the entity’s mentions and how those categories plausibly drive the observed polarity (e.g., police entities co-occurring with crime reports).
5. Use the qualitative summary to contextualize the aggregate chart and to frame conclusions as *patterns in coverage* rather than judgments about an entity.
