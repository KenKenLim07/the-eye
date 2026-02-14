# Data Flow Diagram - Sentiment Analysis of the Philippine Media News Using Natural Language Processing

## Group Members
- Lim, Jose Marie G.
- Tibobos, Romer John
- Edis, Niño Justin
- Gatoteo, Kim Martin T.
- Lenciano, Peter Ritson G.

## Level 0 - Context Diagram (Your Version - Enhanced)

```mermaid
flowchart TD
    E1["User / Researcher"]
    E2["External News Sources\n(Inquirer, GMA, Rappler, etc.)"]

    E1 -->|"search filters, requests"| P1["User Interaction Management\n(Next.js Frontend)"]
    P1 -->|"validated queries"| P2["News Article Collection\n(Scrapers via Celery)"]

    E2 -->|"news articles (HTML)"| P2
    P2 -->|"collected articles"| D1[("Article Repository\n(Supabase: articles table)")]

    D1 -->|"stored articles"| P3["Data Preprocessing\n(Normalize & Clean)"]
    P3 -->|"cleaned and structured data"| D3[("Temporary Processing Storage\n(Redis Cache)")]

    D3 -->|"processed data"| P4["Sentiment and Bias Analysis\n(ML/NLP Models)"]
    P4 -->|"sentiment scores, bias indicators"| D2[("Analysis Results Database\n(Supabase: bias_analysis table)")]

    D2 -->|"analysis summaries, metrics"| P5["Results Generation and Visualization\n(FastAPI Backend)"]
    P5 -->|"charts, tables, insights"| E1
    
    P2 -.->|"background processing"| P4
    D1 -.->|"query articles"| P5
```

## Level 0 - Pure DFD Version (Your Original - Clean)

```mermaid
flowchart TD
    E1["User / Researcher"]
    E2["External News Sources"]

    E1 -->|"search filters, requests"| P1["User Interaction Management"]
    P1 -->|"validated queries"| P2["News Article Collection"]

    E2 -->|"news articles"| P2
    P2 -->|"collected articles"| D1[("Article Repository")]

    D1 -->|"stored articles"| P3["Data Preprocessing"]
    P3 -->|"cleaned and structured data"| D3[("Temporary Processing Storage")]

    D3 -->|"processed data"| P4["Sentiment and Bias Analysis"]
    P4 -->|"sentiment scores, bias indicators"| D2[("Analysis Results Database")]

    D2 -->|"analysis summaries, metrics"| P5["Results Generation and Visualization"]
    P5 -->|"charts, tables, insights"| E1
```

## Why Your Version is Better for Thesis:

1. **Proper DFD Notation**: Uses E (External), P (Process), D (Data Store) conventions
2. **Abstract & Conceptual**: Focuses on logical flow, not implementation details
3. **Cleaner**: Easier to understand at a high level
4. **Academic Standard**: More appropriate for CS thesis documentation

## Recommendations:

1. **Add title and group members** as text above/below the diagram in your thesis document (not in the diagram itself - keeps it cleaner)
2. **Consider adding a feedback loop**: Show that analysis results can trigger re-analysis or updates
3. **Add cache flow**: Show that D3 (cache) is also queried by P5 for faster responses

## Enhanced Version with Feedback Loops:

```mermaid
flowchart TD
    E1["User / Researcher"]
    E2["External News Sources"]

    E1 -->|"search filters, requests"| P1["User Interaction Management"]
    P1 -->|"validated queries"| P2["News Article Collection"]

    E2 -->|"news articles"| P2
    P2 -->|"collected articles"| D1[("Article Repository")]

    D1 -->|"stored articles"| P3["Data Preprocessing"]
    P3 -->|"cleaned and structured data"| D3[("Temporary Processing Storage")]

    D3 -->|"processed data"| P4["Sentiment and Bias Analysis"]
    P4 -->|"sentiment scores, bias indicators"| D2[("Analysis Results Database")]

    D2 -->|"analysis summaries, metrics"| P5["Results Generation and Visualization"]
    P5 -->|"charts, tables, insights"| E1
    
    D1 -.->|"query for analysis"| P4
    D2 -.->|"cached results"| P5
    D3 -.->|"cached aggregates"| P5
```
