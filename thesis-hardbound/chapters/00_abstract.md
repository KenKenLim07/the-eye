# Abstract

The rapid growth of online journalism has made it increasingly difficult to systematically monitor how news is reported across multiple sources. With articles published continuously, identifying patterns in tone, coverage, and narrative framing through manual analysis is no longer practical. This creates a need for automated tools that can organize and analyze large-scale news data in a timely and reproducible way.

This study presents **PH VibeCheck AI**, an end-to-end web-based analytics platform designed to collect, process, and visualize Philippine digital news articles through continuous scheduled ingestion. The system integrates automated web scraping, text normalization, **hybrid sentiment analysis** combining a Tagalog/Taglish-adapted VADER pathway and an English-oriented DistilBERT (SST-2) pathway, and named entity recognition to transform unstructured news content into structured analytical signals.

The platform aggregates articles from multiple outlets into a centralized interface, providing sentiment-labeled streams, entity-level summaries, and cross-source comparison views. Visualization components, including temporal trend dashboards and correlation views, support analysis of how sentiment patterns evolve over time and differ across sources, while preserving the need for qualitative verification at the article level.

Experimental results from a fixed seven-day observation window (2026-03-25 to 2026-03-31) demonstrate the system’s ability to produce repeatable sentiment and entity signals that support exploratory monitoring of Philippine online news. Overall, the study contributes an integrated pipeline and interactive monitoring platform that can serve as a foundation for further work in computational media analysis and journalism analytics.

**Keywords:** Natural Language Processing, sentiment analysis, hybrid sentiment, VADER, DistilBERT, Philippine online news, named entity recognition, news monitoring, correlation analysis

