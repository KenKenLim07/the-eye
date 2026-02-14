# Data Flow Diagram - Sentiment Analysis of the Philippine Media News Using Natural Language Processing

## Group Members
- Lim, Jose Marie G.
- Tibobos, Romer John
- Edis, Niño Justin
- Gatoteo, Kim Martin T.
- Lenciano, Peter Ritson G.

## System Data Flow Diagram

```mermaid
flowchart TB
  titleNode["Sentiment Analysis of the Philippine Media News\nUsing Natural Language Processing"]
  membersNode["Group Members:\nLim, Jose Marie G.\nTibobos, Romer John\nEdis, Niño Justin\nGatoteo, Kim Martin T.\nLenciano, Peter Ritson G."]
  
  user["User/Researcher"]
  frontend["Next.js Frontend\n(pages, lib fetches)"]
  backend["FastAPI Backend\n(/articles, /ml/*, /bias/*, /scrape/run)"]
  cache["Redis Cache"]
  db["Supabase/Postgres\n(articles, bias_analysis)"]
  celeryQ["Celery Queue"]
  scrapers["Scrapers\n(Inquirer, GMA, etc.)"]
  ml["ML/NLP Analysis\n(Sentiment, Bias, Funds)"]
  newsSites["External News Sites"]

  titleNode -.->|"Project Title"| user
  membersNode -.->|"Developed by"| frontend

  user -->|"browse UI,\nselect filters"| frontend
  frontend -->|"API calls (JSON)"| backend

  backend -->|"read/write"| db
  backend -->|"read/write"| cache
  backend -->|"enqueue scrape\n& analysis tasks"| celeryQ

  celeryQ --> scrapers
  celeryQ --> ml

  scrapers -->|"HTTP GET"| newsSites
  scrapers -->|"parsed articles"| db

  ml -->|"insert/update\nanalysis rows"| db
  backend -->|"JSON responses\n(articles + metrics)"| frontend
  frontend -->|"render tables/charts"| user
```

## Recommended Version (Title and Members as Header Nodes)

```mermaid
flowchart TB
  titleNode["Sentiment Analysis of the Philippine Media News\nUsing Natural Language Processing"]
  membersNode["Group Members:\nLim, Jose Marie G. | Tibobos, Romer John | Edis, Niño Justin\nGatoteo, Kim Martin T. | Lenciano, Peter Ritson G."]
  
  user["User/Researcher"]
  frontend["Next.js Frontend\n(pages, lib fetches)"]
  backend["FastAPI Backend\n(/articles, /ml/*, /bias/*, /scrape/run)"]
  cache["Redis Cache"]
  db["Supabase/Postgres\n(articles, bias_analysis)"]
  celeryQ["Celery Queue"]
  scrapers["Scrapers\n(Inquirer, GMA, etc.)"]
  ml["ML/NLP Analysis\n(Sentiment, Bias, Funds)"]
  newsSites["External News Sites"]

  titleNode -.->|"Project Title"| user
  membersNode -.->|"Developed by"| frontend

  user -->|"browse UI,\nselect filters"| frontend
  frontend -->|"API calls (JSON)"| backend

  backend -->|"read/write"| db
  backend -->|"read/write"| cache
  backend -->|"enqueue scrape\n& analysis tasks"| celeryQ

  celeryQ --> scrapers
  celeryQ --> ml

  scrapers -->|"HTTP GET"| newsSites
  scrapers -->|"parsed articles"| db

  ml -->|"insert/update\nanalysis rows"| db
  backend -->|"JSON responses\n(articles + metrics)"| frontend
  frontend -->|"render tables/charts"| user
```

## Alternative Version (Simpler Layout)

If the above version has rendering issues, use this simpler version:

```mermaid
flowchart TB
  user["User/Researcher"]
  frontend["Next.js Frontend\n(pages, lib fetches)"]
  backend["FastAPI Backend\n(/articles, /ml/*, /bias/*, /scrape/run)"]
  cache["Redis Cache"]
  db["Supabase/Postgres\n(articles, bias_analysis)"]
  celeryQ["Celery Queue"]
  scrapers["Scrapers\n(Inquirer, GMA, etc.)"]
  ml["ML/NLP Analysis\n(Sentiment, Bias, Funds)"]
  newsSites["External News Sites"]

  user -->|"browse UI,\nselect filters"| frontend
  frontend -->|"API calls (JSON)"| backend

  backend -->|"read/write"| db
  backend -->|"read/write"| cache
  backend -->|"enqueue scrape\n& analysis tasks"| celeryQ

  celeryQ --> scrapers
  celeryQ --> ml

  scrapers -->|"HTTP GET"| newsSites
  scrapers -->|"parsed articles"| db

  ml -->|"insert/update\nanalysis rows"| db
  backend -->|"JSON responses\n(articles + metrics)"| frontend
  frontend -->|"render tables/charts"| user
```

**Note:** For your thesis document, you can add the title and group members as text above or below the diagram, or include them in the figure caption.
