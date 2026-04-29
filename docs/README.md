# PH Eye Documentation

This folder contains internal documentation for the PH Eye project.

## What The System Does

- Scrapes news articles from supported Philippine online news sources.
- Normalizes URLs and cleaned article text for consistent storage.
- Runs NLP:
  - Sentiment analysis using NLTK VADER (compound score + label).
  - Named Entity Recognition (spaCy) to extract PERSON/ORG/GPE entities for aggregation.
- Exposes a FastAPI backend consumed by the Next.js dashboard (trends, correlation, entity summaries, per-source article views).

## Index

- [ML AI Integration](./ML_AI_INTEGRATION.md)
- [Accuracy Evaluation](./ACCURACY_EVALUATION.md)
- [Layout System](./LAYOUT_SYSTEM.md)
- [AI Summarization Quick Start](./SUMMARIZATION_QUICK_START.md)
- [AI Summarization Implementation](./AI_SUMMARIZATION_IMPLEMENTATION.md)
- [Borrowed Laptop Setup Guide](./BORROWED_LAPTOP_SETUP_GUIDE.md)
- [Windows Defense Runbook](./WINDOWS_DEFENSE_RUNBOOK.md)

Last updated: March 2026
