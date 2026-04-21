# Related Work

This chapter reviews key ideas and prior methods that motivate the design and methodological choices of this study. The review is organized around (1) media framing and agenda-setting, (2) sentiment analysis methods relevant to news text, (3) transformer-based language models used for sentiment classification, and (4) named entity recognition for entity-level aggregation.

## Media Framing and Agenda-Setting in News

Media effects research emphasizes that news content is not only a vehicle for facts, but also a carrier of *tone*, *emphasis*, and *framing*. Framing theory explains how the presentation of an issue can influence how audiences interpret and evaluate events [@entman1993framing]. Complementing this view, agenda-setting theory suggests that sustained attention and repeated coverage can shape which topics are perceived as salient or important in public discourse [@mccombs1972agenda].

These theories motivate the central design of this study: rather than treating news monitoring as a purely qualitative activity that does not scale, large-scale collections of news articles can be summarized into interpretable signals. The intent is not to replace human judgment, but to support it by surfacing patterns (e.g., sustained negativity, shifts in tone, or changes in entity prominence) that warrant deeper reading.

Related computational media work has also operationalized source differences through language patterns. Gentzkow and Shapiro introduce a measurable notion of media “slant” based on similarity of outlet language to partisan speech, illustrating how textual signals can be aggregated into outlet-level indicators [@gentzkow2010slant]. While sentiment is not equivalent to slant, the general approach—summarizing large corpora into interpretable quantitative signals—supports the feasibility of scalable media monitoring.

In the Philippine context, watchdog and transparency initiatives reinforce the same scalability constraint. CMFR’s election-period monitoring and reporting demonstrates the value of systematic observation grounded in manual review, but such efforts necessarily operate within time and resource limits [@cmfr2022mediaelections]. Likewise, Media Ownership Monitor Philippines (MOM-PH) provides public documentation of ownership structures relevant to media accountability, but updates involve investigative data collection and verification that is not continuous [@momph2023]. These efforts motivate complementary automated tools that can track signals over time and across sources, while preserving the role of qualitative interpretation and editorial judgment.

Beyond salience and framing, research also shows that audiences can be more sensitive to negative information in news consumption. Soroka et al. report cross-national evidence of a negativity bias in psychophysiological reactions to news, supporting the idea that emotional tone is not only stylistic but can affect attention and interpretation [@soroka2019negativity]. This strengthens the relevance of sentiment analysis as a monitoring signal in news domains, especially when paired with careful neutral handling to avoid over-polarizing factual reporting.

## Sentiment Analysis Approaches for News-Style Text

Sentiment analysis aims to estimate the emotional polarity of text (commonly positive, neutral, or negative). In a news domain, sentiment differs from product reviews or social media reactions: many passages are factual and “reporting-like,” where the correct label is often neutral even though the topic itself may be serious (e.g., investigations, disasters, policy debates). This creates a practical challenge for both lexicon-based and learned models: *how to avoid over-polarizing objective reporting*.

Survey work in sentiment analysis distinguishes between polarity classification, aspect/target sentiment, and broader opinion mining tasks, highlighting that model choice and evaluation should match the text type and the intended use of outputs [@pang2008opinionmining; @liu2012sentiment]. This is especially relevant for news, where “neutral reporting” is common and sentiment is often used as a monitoring signal rather than a definitive label.

### Lexicon-based sentiment (VADER)

VADER (Valence Aware Dictionary and sEntiment Reasoner) is a widely used lexicon- and rule-based approach that produces a normalized compound sentiment score and can be interpreted as a lightweight polarity signal [@hutto2014vader]. Lexicon-based systems are attractive for transparency: individual tokens and simple heuristics explain why a score was produced, and behavior can be modified via controlled lexicon updates.

However, the default VADER lexicon is English-centric, which can be insufficient in multilingual settings where common affective terms are Tagalog or code-switched (Taglish). This motivates the Philippine Tagalog/Taglish lexicon patch used in this thesis: extending the lexicon and adding deterministic phrase normalization to improve coverage on locally frequent expressions (details in Chapter 4 and Appendix B).

Lexicon-based sentiment has a longer tradition beyond VADER, including semantic-orientation approaches for unsupervised polarity classification [@turney2002thumbs] and dictionary-based systems that explicitly model intensification and negation such as SO-CAL [@taboada2011lexicon]. These directions reinforce why lexicons remain practical in domains where interpretability and controlled updates are important.

### Philippine sentiment and low-resource NLP studies

Prior studies in the Philippine context highlight both domain-specific challenges and the need for localized baselines. Diaz examined sentiment polarity identification for banner headlines in Philippine broadsheets, illustrating that news-style text can require careful handling to avoid misinterpreting objective reporting as emotional language [@diaz2021broadsheets]. More broadly, Cruz and Cheng established benchmark results for text classification in low-resource languages, including Filipino, showing that modern transformer approaches can outperform traditional methods when adapted to local data [@cruzcheng2020lowresource].

Other Philippine-focused work demonstrates adjacent applications of sentiment and topic signals. Garcia analyzed COVID-19 sentiment from Metro Manila via social media text, illustrating that automated sentiment can track public affect in response to evolving events [@garcia2020covidph]. In news-style corpora, research has explored using sentiment features alongside topic models for tasks such as fake news detection [@spp2023fake_news_lda]. Institutional publications also reflect growing interest in quantitative news sentiment as a signal, such as data science work in central banking contexts [@bis2025ifc64], and policy-focused sentiment analysis in Philippine settings [@pids_likecommentshare].

### Neutral handling as a first-class requirement

A recurring theme in this project is that “neutral” should be treated as a meaningful class for news monitoring. For lexicon-based sentiment, neutral handling can be operationalized by widening the neutral band around zero so that borderline scores are treated as neutral. For learned binary models, neutrality must be introduced via abstention rules (e.g., confidence thresholds) rather than explicit training, which has implications for evaluation and interpretation (see Chapter 5).

## Transformer Models for Sentiment Classification

Transformer-based language models have reshaped NLP by enabling strong performance across classification tasks via pretraining and fine-tuning. BERT provides a foundational transformer architecture for language understanding and has become a standard baseline in text classification pipelines [@devlin2018bert]. DistilBERT is a distilled variant designed to retain much of BERT’s performance while reducing computational cost, making it practical for CPU inference in constrained environments [@sanh2019distilbert].

These models build on the transformer architecture introduced by Vaswani et al., which replaces recurrence with attention-based sequence modeling and enables high parallelism during training and inference [@vaswani2017attention].

### SST-2 as an accessible sentiment baseline

The Stanford Sentiment Treebank (SST) provides widely used sentiment benchmarks, and SST-2 is a commonly used binary (positive vs. negative) formulation for fine-tuning transformer sentiment classifiers [@socher2013sst]. The advantage of using an SST-2–fine-tuned model is availability and reproducibility: it offers a stable baseline for sentiment scoring when the input is English-heavy.

At the same time, SST-2’s binary objective creates a known limitation for news: objective reporting often requires a neutral category, and the model is not trained to represent neutrality explicitly. For this reason, the study treats the transformer output as a polarity estimate that can be thresholded into neutral under low confidence, rather than as a direct three-class predictor (see Chapter 4 and Chapter 5).

### Practical deployment considerations (CPU bounds and reproducibility)

For deployment in a scheduled, containerized pipeline, transformer inference must be operationally bounded. In practice, this motivates (1) input truncation for long articles, (2) persistent caching of model weights for repeatable runs, and (3) CPU-friendly inference paths that do not require scarce GPU resources. These constraints are particularly important in news monitoring, where the daily workload can include long editorials and continuous ingestion across multiple sources.

In addition, widely used open-source implementations provide standardized tokenization and model loading behavior, which can improve reproducibility and reduce engineering variance across environments [@wolf2020transformers].

### Hybrid and targeted sentiment directions

Hybrid sentiment approaches are commonly used to balance interpretability and robustness—combining rule/lexicon signals with learned representations to improve behavior under domain shift and mixed-language inputs [@kiritchenko2014informal]. In addition, targeted sentiment work motivates entity-aware analysis, where polarity is associated with specific actors or topics rather than only document-level labels [@mitchell2013targeted]. These perspectives align with the approach in this study: the implemented pipeline supports entity-aware aggregation and navigation while treating sentiment outputs as signals for monitoring rather than definitive judgments.

## Named Entity Recognition (NER) for Entity-Level Media Analysis

News monitoring is often entity-centered: audiences track people, organizations, and places. Named Entity Recognition (NER) supports this by extracting structured entity spans from unstructured text, enabling aggregation such as “top mentioned entities” and “average sentiment when an entity is mentioned.” Classic NER surveys describe the core challenge: identifying and classifying entity mentions reliably across diverse text [@nadeau2007ner].

Standard evaluation datasets and neural sequence labeling approaches provide practical foundations for applied NER systems. The CoNLL-2003 shared task formalized a widely used benchmark for language-independent NER [@tjong2003conll], and later neural architectures using character-aware models and sequence labeling improved performance without heavy hand-crafted features [@lample2016neural].

Entity-level analysis is also conceptually aligned with media studies: attention and framing frequently center on specific actors (e.g., political figures, agencies, or locations), and shifts in which entities are foregrounded can reflect issue salience. As a result, entity extraction supports monitoring not only of overall tone, but of *who* is being talked about and how coverage patterns shift over time.

In the implemented pipeline, entity extraction is performed using a standard NER pipeline. While general-purpose NER offers practical performance, entity extraction in Philippine news remains challenging due to local naming conventions, abbreviations, and overlapping acronyms. This motivates future work in entity disambiguation and PH-specific NER enhancements (discussed in Chapter 6).

## Synthesis and Research Gap

The reviewed literature supports the feasibility of computational signals for news monitoring, but also indicates several gaps when applied to Philippine online news. First, existing Philippine-focused monitoring efforts and studies demonstrate value but are constrained in scale, temporal coverage, or update frequency due to manual processes [@cmfr2022mediaelections; @momph2023; @diaz2021broadsheets]. Second, widely used sentiment tools such as VADER are English-centric, motivating controlled localization for Tagalog/Taglish expressions. Third, strong transformer baselines such as SST-2–fine-tuned models are commonly binary, creating a mismatch with news-style neutrality that requires operational abstention rules rather than direct three-class prediction [@socher2013sst]. Finally, although entity-level and targeted sentiment directions motivate actor-centered monitoring [@mitchell2013targeted], applied systems often stop at document-level summaries without integrating entity aggregation into a continuous, multi-source pipeline.

This study addresses these gaps by implementing a hybrid, operationally constrained sentiment pipeline for Philippine online news that combines (a) a transparent lexicon-based baseline (VADER) with localized coverage via a controlled Tagalog/Taglish patch, (b) a lightweight transformer path for English-heavy text under CPU and truncation constraints, and (c) entity extraction to enable actor-centered aggregation and dashboard-based exploration of trends.

## Conceptual Contribution

Building on these gaps, the study contributes a *signal-based* view of news analytics: sentiment and entity extraction are treated as scalable indicators that support interpretation, rather than as direct measures of intent or definitive labels of bias. Conceptually, this frames the role of NLP in media monitoring as (1) summarizing large text streams into interpretable time-series and actor-centered views, and (2) enabling systematic comparison across outlets while preserving the need for qualitative reading and contextual judgment.

## Summary

Prior work motivates three key design requirements that shape the approach in this study:
1. **Interpretability and auditability:** lexicon-based sentiment (VADER) provides transparent signals and is adaptable via controlled patching [@hutto2014vader].
2. **Robustness and efficiency:** transformers (DistilBERT distilled from BERT) provide strong English sentiment performance at practical CPU cost [@devlin2018bert; @sanh2019distilbert].
3. **Entity-centric analysis:** NER enables aggregation and navigation beyond document-level sentiment, supporting exploratory media analysis workflows [@nadeau2007ner].

Together, these strands of prior work establish the foundation for a hybrid, signal-based approach to media monitoring—one that integrates interpretable sentiment analysis, efficient transformer models, and entity-level aggregation to address the limitations of existing methods in the Philippine news context [@entman1993framing; @mccombs1972agenda].
