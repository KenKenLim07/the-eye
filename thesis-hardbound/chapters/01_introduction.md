# Introduction

## Background of the Study

Digital publishing has transformed how people access, share, and interpret information. News that previously depended on print circulation or scheduled broadcast can now be published and distributed online continuously. In the Philippines, where internet and social media usage is widespread, online platforms have become a primary channel for news consumption. As of early 2025, the country recorded approximately 97.5 million internet users, representing an online penetration rate of 83.8 percent [@datareportal]. This environment increases both the availability of information and the difficulty of monitoring it systematically.

In practice, the speed, volume, and fragmentation of online publishing create a persistent monitoring gap: by the time one topic is reviewed, many new articles have already appeared across multiple outlets. Major Philippine news organizations continue to follow established reporting standards, but the transition to digital platforms has introduced new pressures shaped by algorithm-driven distribution, where engagement metrics can influence how content is prioritized and surfaced. As a result, differences in emphasis, tone, and narrative framing across sources can emerge even when reporting on the same events.

Beyond volume, the online information environment also amplifies the consequences of misleading or low-quality content spreading quickly through social networks, which strengthens the practical case for tools that support timely monitoring and verification workflows [@lazer2018fakenews; @vosoughi2018spread].

Media effects research provides theoretical grounding for examining variations in tone and coverage across news sources. Framing theory explains how the selection and emphasis of textual elements influence interpretation [@entman1993framing], while agenda-setting theory suggests that sustained coverage shapes the perceived importance of issues [@mccombs1972agenda]. In addition, the affective dimension of news—particularly emotional tone—plays a role in audience perception and engagement [@soroka2019negativity]. In the Philippine context—characterized by diverse outlets and rapidly shifting public attention due to elections, disasters, and policy developments—these differences in framing and tone become especially relevant for systematic analysis.

Despite the importance of such analysis, existing approaches to media monitoring remain limited in scalability. Manual content analysis provides depth but is time-intensive and difficult to sustain across continuous publication streams and multiple sources. For example, the Center for Media Freedom and Responsibility (CMFR), in its 2022 election coverage study, recorded 1,972 election-related reports over a defined monitoring period [@cmfr2022mediaelections]. Similarly, initiatives such as Media Ownership Monitor Philippines (MOM-PH) rely on extensive manual data collection and verification, resulting in periodic rather than continuous updates [@momph2023]. These constraints highlight the need for more efficient and scalable analytical approaches.

Natural Language Processing (NLP) offers practical techniques for analyzing large collections of text, including sentiment analysis and named entity recognition [@pang2008opinionmining; @nadeau2007ner]. When applied to online news, these methods can produce structured summaries such as sentiment distributions over time and entity-level mention patterns across sources. In this thesis, such outputs are treated as *signals*: compressed representations of large text corpora that support interpretation and guide deeper qualitative analysis, rather than serving as definitive judgments about bias or intent.

Motivated by these needs, this capstone project develops PH VibeCheck AI: an end-to-end system that continuously collects Philippine online news, applies hybrid sentiment analysis and entity extraction, and presents results through interactive dashboards for trend monitoring, cross-source comparison, and article-level verification.

## Statement of the Problem

**General Problem.** There remains a gap between the pace of online news publication and the pace of careful interpretation. Philippine news audiences encounter large volumes of articles across outlets, but the ability to systematically monitor shifts in sentiment and the context in which entities are discussed is limited by time and tooling constraints. This capstone project addresses the gap by designing and implementing **PH VibeCheck AI**, an end-to-end web-based system that continuously collects Philippine online news articles, applies hybrid sentiment analysis and entity extraction, and visualizes results through interactive dashboards.

Specifically, this study seeks to answer the following questions:

1. What is the overall sentiment distribution (positive, neutral, negative) across major Philippine news sources within a defined observation window?
2. How do sentiment trends vary over time (e.g., daily patterns in a 7-day window), and how do sources differ in coverage and sentiment volume?
3. Which entities (persons, organizations, and locations) are most frequently mentioned, and what average sentiment is associated with their coverage?
4. How do sentiment signals across outlets relate to each other over time (e.g., aligned vs. opposing trends) based on correlation of daily average sentiment?
5. How effective is a hybrid sentiment approach (Taglish VADER + DistilBERT SST-2) in handling Philippine news text compared to single-model baselines?

## Objectives of the Study

The general objective of this study is to design and implement a deployable pipeline and monitoring interface for sentiment and entity-level analysis of Philippine online news.

Specifically, the study aims to:
1. Build an automated ingestion pipeline that collects and normalizes articles from multiple Philippine news outlets on a scheduled basis.
2. Implement a **hybrid sentiment engine** that is robust to multilingual and code-switched (Taglish) text by combining:
   - a lexicon-based analyzer (VADER) [@hutto2014vader] extended with a Philippine Tagalog/Taglish patch, and
   - a lightweight transformer classifier (DistilBERT) [@sanh2019distilbert; @devlin2018bert] fine-tuned on SST-2 [@socher2013sst].
3. Extract named entities (PERSON/ORG/GPE) using NER to support entity-level aggregation and cross-source comparisons [@nadeau2007ner].
4. Provide dashboards that support:
   - monitoring sentiment distributions and temporal trends,
   - comparing outlets via correlation of daily sentiment signals, and
   - navigating from aggregate views to individual articles for qualitative verification.
5. Evaluate the sentiment engine using a Taglish/Tagalog gold set and a manually labeled benchmark sample, and complement these with drift checks on real collected articles.

## Scope and Delimitations

This study focuses on the development and evaluation of an automated system for monitoring sentiment patterns in Philippine online news. The system collects articles from a fixed set of implemented news sources—ABS-CBN News, GMA News Online, Philippine Daily Inquirer, Rappler, Manila Bulletin, The Manila Times, The Philippine Star, and SunStar—and processes both English and Tagalog/Taglish (code-switched) text commonly found in Philippine news publishing. Data collection is performed continuously; however, the results reported in this thesis are based on a defined 7-day observation window (2026-03-25 to 2026-03-31) to provide a consistent snapshot for analysis.

The scope of analysis is limited to the textual content of news articles, including headlines and body text. Multimedia elements such as images, videos, advertisements, embedded social media content, and user comment sections are excluded. The system generates sentiment scores and labels, as well as entity-level aggregates, which are treated as exploratory analytical signals rather than definitive measures of bias or intent.

The implemented sentiment approach combines a lexicon-based method (VADER with a Tagalog/Taglish extension) with a transformer-based baseline (DistilBERT SST-2) for English-heavy text. However, the study does not implement or evaluate a fully multilingual transformer sentiment model, since Tagalog/Taglish handling is performed through a localized lexicon-based pathway. The study does not attempt to infer author intent or establish ground truth for editorial bias, as such interpretations require deeper qualitative and contextual analysis beyond automated techniques. Furthermore, the study does not redistribute full publisher article content; only derived outputs such as sentiment scores, entity data, and aggregated results are used for reporting.

## Conceptual Framework (IPO Model)

To guide the system design, this study adopts an Input–Process–Output (IPO) view of the pipeline: the system ingests raw news articles (inputs), transforms them using scraping and NLP components (process), and produces dashboards and structured summaries (outputs). A visual IPO diagram will be inserted in the final manuscript to illustrate this flow.

**Figure 1. Conceptual Framework of the Study (IPO).** The IPO framework summarizes how raw news data is collected, processed through analytical methods, and transformed into interpretable outputs for media sentiment monitoring.

| Component | Description |
|---|---|
| **Input** | Philippine online news articles (URL, title, content, source, timestamps) collected from multiple outlets. |
| **Process** | (1) URL discovery and scraping; (2) cleaning/normalization; (3) hybrid sentiment scoring (Taglish VADER + DistilBERT SST-2 via routing); (4) named entity extraction; (5) aggregation and caching for analytics. |
| **Output** | Interactive dashboards and data products: latest headlines, KPI snapshots, sentiment trends, cross-source correlation views, and entity frequency/sentiment summaries; plus reproducible evaluation reports. |

The **Input** component represents the raw textual evidence used in the study. These inputs include article pages retrieved from selected Philippine news sources and the extracted text fields (headline and body) together with minimal metadata (e.g., URL, source, and publication timestamp). Inputs are treated as an evolving stream, since news sites publish continuously.

The **Process** component represents the end-to-end analytical pipeline applied to convert raw text into consistent, queryable signals. First, the scraping layer discovers and retrieves article content. Second, the system performs basic normalization (e.g., field cleaning and metadata standardization) so that articles from different outlets can be analyzed in a comparable format. Third, sentiment is computed using a hybrid approach designed for mixed-language Philippine news: Tagalog/Taglish-heavy text is handled by the localized VADER pathway, while English-heavy text can be routed to a lightweight transformer baseline, with conservative truncation to remain feasible in scheduled CPU workloads. Fourth, named entities (persons, organizations, and locations) are extracted so that results can be aggregated at the actor level. Finally, the processed outputs are aggregated into time-series summaries and cached views to support dashboard queries.

The **Output** component consists of the system’s structured results and visual summaries. Outputs include per-article sentiment scores and labels, extracted entities, and aggregated views such as daily sentiment trends, cross-source comparisons, correlation of sentiment time-series, and entity frequency/sentiment summaries. These outputs are presented through interactive dashboards to support monitoring and exploration, and through reproducible evaluation reports that quantify model behavior on defined test sets.

## Significance of the Study

PH VibeCheck AI demonstrates how an automated pipeline can support systematic observation of media discourse at scale. By combining continuous collection, hybrid sentiment scoring, entity extraction, and dashboard-level aggregation, the system provides interpretable signals (not definitive judgments) that can guide deeper qualitative reading.

The significance of this study can be observed across multiple stakeholder groups:

**Media organizations and newsrooms.**  
The platform provides data-driven indicators that may support internal reflection on reporting tone across time and across outlets. Sentiment distributions, trend summaries, and entity-level views can help newsrooms identify periods where coverage becomes more polarized or where certain entities dominate the news cycle—without replacing editorial judgment.

**Media watchdogs and fact-checking institutions (e.g., CMFR, VERA Files).**  
Organizations focused on accountability can use automated monitoring as a complement to manual review. Cross-source comparisons and correlation views can surface sustained shifts in tone or coverage alignment/divergence that warrant deeper investigation using traditional content analysis.

**The general public and digital news consumers.**  
Interactive dashboards can support media literacy by allowing readers to observe how emotional tone evolves across outlets and over time. Presenting large volumes of articles in summarized visual form encourages more critical interpretation than relying on isolated articles.

**Policymakers and communication agencies.**  
Aggregated sentiment indicators may serve as supplementary signals when examining how policy-related topics are portrayed in the public information environment. The system’s intent is exploratory: to assist monitoring and prioritization rather than to provide authoritative evaluations.

**Academic researchers and NLP practitioners.**  
The thesis contributes a reproducible reference implementation of a production-style NLP pipeline for Philippine news monitoring. It integrates a Tagalog/Taglish-adapted VADER pathway [@hutto2014vader] with a lightweight transformer baseline (DistilBERT SST-2) [@sanh2019distilbert; @devlin2018bert; @socher2013sst] through an auditable routing mechanism, and documents evaluation assets and procedures that can be extended in future work.

## Definition of Terms

The following terms are used throughout this thesis:
- **Natural Language Processing (NLP):** computational methods for analyzing and processing human language text [@pang2008opinionmining; @liu2012sentiment].
- **Media sentiment (tone):** the overall emotional polarity conveyed by news content, treated in this study as an exploratory signal for monitoring and comparison rather than a definitive measure of bias or intent [@entman1993framing; @pang2008opinionmining].
- **Framing:** the selection and emphasis of textual elements that shape how audiences interpret issues and events [@entman1993framing].
- **Agenda-setting:** the idea that sustained media attention influences which issues the public perceives as salient or important [@mccombs1972agenda].
- **Sentiment analysis:** an NLP task that estimates polarity (e.g., positive, neutral, negative) expressed in text [@pang2008opinionmining; @liu2012sentiment].
- **Polarity:** the directional orientation of sentiment in text, represented as a numeric score or categorical label (positive/neutral/negative) [@pang2008opinionmining; @liu2012sentiment].
- **Article:** a normalized record representing a news item (e.g., URL, title, content, source, and timestamps).
- **Sentiment score (compound):** a numeric polarity score in the range $[-1,1]$ used to summarize article tone (negative to positive).
- **Sentiment label:** a categorical interpretation of the sentiment score: positive, neutral, or negative (based on thresholds/neutral band).
- **Neutral band:** a configurable threshold region around zero where borderline sentiment scores are mapped to the neutral label to reduce over-polarizing factual reporting text.
- **Hybrid sentiment engine:** a sentiment approach that routes an article to either the Taglish VADER pathway or the DistilBERT pathway depending on language-signal heuristics.
- **VADER:** a lexicon- and rule-based sentiment model used as the interpretable pathway in the hybrid design [@hutto2014vader].
- **Philippine Tagalog/Taglish patch:** a versioned extension to VADER’s lexicon and phrase rules to improve coverage on Tagalog/Taglish expressions.
- **DistilBERT (SST-2):** a lightweight transformer-based sentiment classifier fine-tuned on SST-2, used primarily for English-heavy inputs [@sanh2019distilbert; @devlin2018bert; @socher2013sst].
- **Named Entity Recognition (NER):** an NLP task that identifies and classifies entity mentions such as persons, organizations, and locations in text [@nadeau2007ner].
- **Web scraping:** automated retrieval and extraction of structured text fields (e.g., title and article body) from news websites for downstream analysis.
- **Dashboard:** an interactive interface that summarizes and visualizes aggregated outputs (e.g., sentiment trends, cross-source comparisons, entity rankings) and supports drill-down to article-level views for qualitative verification.
- **Gold set:** a small, fixed labeled dataset used for controlled regression testing of model behavior on representative examples.
- **Manual benchmark:** a human-labeled sample of real articles used to evaluate end-to-end model accuracy and error patterns in authentic news text.
- **Drift check:** a comparison of old vs. new model outputs on sampled real articles to surface large behavior changes for audit and explanation.
- **Source (outlet):** a news organization or publication from which articles are collected (e.g., GMA, ABS-CBN, Rappler).
- **Correlation (Pearson $r$):** a statistic used to quantify linear association between two sources’ daily average sentiment trends.

## Organization of the Thesis

This thesis is organized as follows:
- Chapter 2 reviews related work in sentiment analysis, NLP for news, and computational media analysis.
- Chapter 3 discusses the technicality of the project, including the system architecture, technology stack, and key implementation components of the pipeline.
- Chapter 4 presents the design and methodology, including data collection and normalization, NLP analysis approach, and evaluation procedures.
- Chapter 5 reports the results and discussion, including benchmark outcomes, sentiment distributions, temporal trends, cross-source correlation, and entity-level patterns.
- Chapter 6 concludes the study with limitations and recommendations.
