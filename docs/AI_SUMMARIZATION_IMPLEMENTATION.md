# 🤖 AI Summarization Implementation Guide

## 📋 Overview

This document provides a complete implementation guide for adding AI-powered text summarization to the PH-Eye news aggregator platform. The feature will automatically generate concise summaries of news articles using state-of-the-art transformer models.

## 🎯 Goals

- **Automated Summarization**: Generate 2-3 sentence summaries of news articles
- **Real-time Processing**: Summarize articles as they're scraped
- **User Experience**: Display summaries in article cards and quick view modals
- **Thesis Enhancement**: Demonstrate complete ML pipeline (Sentiment + Bias + Summarization)

## 🏗️ Architecture

### Current System Integration
```
News Articles → Scraping → Text Extraction → ML Pipeline → Database
                                    ↓
                            [Sentiment + Bias + Summarization]
                                    ↓
                              Frontend Display
```

### Database Schema
**No new table required!** Uses existing `bias_analysis` table:

```sql
-- Existing table supports summarization
INSERT INTO bias_analysis (
    article_id,
    model_type,        -- 'summarization'
    model_version,     -- 'bart_large_cnn_v1'
    confidence_score,
    model_metadata     -- {"summary": "Generated summary text", ...}
) VALUES (...);
```

## 🛠️ Implementation Options

### Option 1: Hugging Face BART (RECOMMENDED)
**Cost**: FREE
**Quality**: High
**Memory**: ~1.5GB RAM
**Speed**: 2-5 seconds per article

```python
from transformers import pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
```

### Option 2: Kagi Universal Summarizer
**Cost**: $0.030 per 1,000 tokens
**Quality**: Enterprise-grade
**Memory**: Minimal (API-based)
**Speed**: <1 second per article

### Option 3: ZeroGPT API
**Cost**: Free tier available
**Quality**: Good
**Memory**: Minimal (API-based)
**Speed**: 1-2 seconds per article

## 📁 File Structure

```
backend/
├── app/
│   ├── ml/
│   │   ├── bias.py              # Existing bias analysis
│   │   └── summarization.py     # NEW: Summarization module
│   ├── workers/
│   │   └── ml_tasks.py          # UPDATED: Add summarization task
│   └── main.py                  # UPDATED: Add summarization endpoint
├── requirements.txt             # UPDATED: Add transformers
└── Dockerfile                   # UPDATED: Add model dependencies

frontend/
├── src/
│   ├── components/
│   │   └── articles/
│   │       └── article-cards-interactive.tsx  # UPDATED: Display summaries
│   └── lib/
│       └── articles.ts          # UPDATED: Fetch summaries
```

## 🔧 Implementation Steps

### Step 1: Backend ML Module (30 minutes)

Create `backend/app/ml/summarization.py`:

```python
import time
from typing import Tuple, Dict, Any
import torch
from transformers import pipeline

# Global model cache
_summarizer = None
_model_name = "facebook/bart-large-cnn"

def _ensure_summarizer():
    """Lazy load the summarization model."""
    global _summarizer
    if _summarizer is not None:
        return _summarizer
    
    try:
        device = 0 if torch.cuda.is_available() else -1
        _summarizer = pipeline(
            "summarization",
            model=_model_name,
            device=device,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        )
        return _summarizer
    except Exception as e:
        raise RuntimeError(f"Failed to initialize summarizer: {e}")

def analyze_text_summarization(text: str) -> Tuple[str, float, Dict[str, Any]]:
    """Generate a summary of the input text."""
    start = time.time()
    
    if not text or len(text.strip()) < 50:
        return "", 0.0, {"error": "Text too short for summarization"}
    
    try:
        summarizer = _ensure_summarizer()
        clean_text = text.strip()
        
        # Truncate if too long (BART has 1024 token limit)
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000] + "..."
        
        result = summarizer(
            clean_text,
            max_length=150,
            min_length=30,
            do_sample=False,
            num_beams=4,
            early_stopping=True
        )
        
        summary = result[0]['summary_text'] if result else ""
        confidence = 0.8
        
        elapsed_ms = (time.time() - start) * 1000.0
        
        metadata = {
            "model": _model_name,
            "processing_time_ms": int(elapsed_ms),
            "input_length": len(text),
            "output_length": len(summary),
            "compression_ratio": len(summary) / len(text) if text else 0
        }
        
        return summary, confidence, metadata
        
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000.0
        return "", 0.0, {
            "error": str(e),
            "processing_time_ms": int(elapsed_ms)
        }

def build_summarization_row(article_id: int, text: str) -> Dict[str, Any]:
    """Build a summarization analysis row for database storage."""
    summary, confidence, metadata = analyze_text_summarization(text)
    
    return {
        "article_id": article_id,
        "model_version": "bart_large_cnn_v1",
        "model_type": "summarization",
        "sentiment_score": None,
        "sentiment_label": None,
        "political_bias_score": None,
        "toxicity_score": None,
        "confidence_score": confidence,
        "processing_time_ms": metadata.get("processing_time_ms", 0),
        "model_metadata": {
            **metadata,
            "summary": summary
        }
    }
```

### Step 2: Update Requirements (1 minute)

Add to `backend/requirements.txt`:

```txt
transformers==4.36.0
torch==2.1.0
```

### Step 3: Update ML Tasks (15 minutes)

Update `backend/app/workers/ml_tasks.py`:

```python
from app.ml.summarization import build_summarization_row

def build_comprehensive_bias_analysis(article_id: int, text: str) -> list[Dict[str, Any]]:
    """Build comprehensive analysis including summarization."""
    rows = []
    
    # Existing analyses
    rows.append(build_bias_row_for_vader(article_id, text))
    rows.append(build_bias_row_for_philippine_political(article_id, text))
    
    # NEW: Add summarization
    rows.append(build_summarization_row(article_id, text))
    
    return rows
```

### Step 4: Add API Endpoint (15 minutes)

Add to `backend/app/main.py`:

```python
@app.get("/ml/summarization")
async def get_summarization(ids: str):
    """Get summarization data for specific articles."""
    try:
        article_ids = [int(id.strip()) for id in ids.split(",") if id.strip()]
    except ValueError:
        return {"error": "Invalid article IDs format"}
    
    sb = get_supabase()
    try:
        result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_type", "summarization").order("created_at", desc=True).execute()
        return {"summaries": result.data or []}
    except Exception as e:
        return {"error": str(e)}
```

### Step 5: Frontend Integration (1-2 hours)

#### Update Article Cards Component

Add to `src/components/articles/article-cards-interactive.tsx`:

```typescript
interface Article {
  id: number;
  title: string;
  url: string;
  content: string;
  published_at: string;
  source: string;
  category?: string;
  sentiment?: string;
  summary?: string; // NEW: Add summary field
}

// In the component:
{sentiment && (
  <Badge variant="outline" className="text-xs">
    {sentiment.toUpperCase()}
  </Badge>
)}

{/* NEW: Add summary display */}
{summary && (
  <div className="mt-2 p-2 bg-blue-50 rounded-md">
    <p className="text-xs text-blue-800 font-medium mb-1">Summary:</p>
    <p className="text-xs text-blue-700">{summary}</p>
  </div>
)}
```

#### Update Article Fetching

Update `src/lib/articles.ts`:

```typescript
export async function fetchArticlesWithSummaries(articleIds: number[]) {
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/ml/summarization?ids=${articleIds.join(',')}`, {
      cache: 'no-store'
    });
    
    if (response.ok) {
      const data = await response.json();
      const summaries: Record<number, string> = {};
      
      data.summaries?.forEach((item: any) => {
        const summary = item.model_metadata?.summary;
        if (summary) {
          summaries[item.article_id] = summary;
        }
      });
      
      return summaries;
    }
  } catch (error) {
    console.error('Error fetching summaries:', error);
  }
  
  return {};
}
```

## 🚀 Deployment

### Docker Updates

Update `backend/Dockerfile`:

```dockerfile
# Add model download step
RUN python -c "from transformers import pipeline; pipeline('summarization', model='facebook/bart-large-cnn')"
```

### Environment Variables

Add to `.env`:

```bash
# Summarization settings
SUMMARIZATION_MODEL=facebook/bart-large-cnn
SUMMARIZATION_MAX_LENGTH=150
SUMMARIZATION_MIN_LENGTH=30
```

## 📊 Performance Considerations

### Memory Usage
- **Current**: ~680MB / 7.6GB (9%)
- **With BART**: ~2.2GB / 7.6GB (29%)
- **Recommendation**: Monitor memory usage, consider GPU if available

### Processing Time
- **BART Model**: 2-5 seconds per article
- **Batch Processing**: Process multiple articles in parallel
- **Caching**: Cache summaries to avoid reprocessing

### Optimization Strategies
1. **Lazy Loading**: Load model only when needed
2. **Batch Processing**: Process multiple articles together
3. **Caching**: Store summaries to avoid reprocessing
4. **GPU Acceleration**: Use CUDA if available

## 🧪 Testing

### Unit Tests

Create `backend/tests/test_summarization.py`:

```python
import pytest
from app.ml.summarization import analyze_text_summarization

def test_summarization():
    text = "This is a long article about Philippine politics..."
    summary, confidence, metadata = analyze_text_summarization(text)
    
    assert len(summary) > 0
    assert confidence > 0
    assert "processing_time_ms" in metadata
```

### Integration Tests

```python
def test_summarization_endpoint():
    response = client.get("/ml/summarization?ids=1,2,3")
    assert response.status_code == 200
    data = response.json()
    assert "summaries" in data
```

## 📈 Monitoring

### Metrics to Track
- **Processing Time**: Average time per article
- **Memory Usage**: Model memory consumption
- **Success Rate**: Percentage of successful summarizations
- **Quality Metrics**: Summary length, compression ratio

### Logging

```python
import logging

logger = logging.getLogger(__name__)

def analyze_text_summarization(text: str):
    logger.info(f"Starting summarization for text length: {len(text)}")
    # ... implementation
    logger.info(f"Summarization completed in {elapsed_ms}ms")
```

## 🔄 Future Enhancements

### Phase 2 Features
1. **Multiple Summary Lengths**: Short, medium, long summaries
2. **Quality Indicators**: Confidence scores, readability metrics
3. **Batch Processing**: Summarize existing articles
4. **Custom Models**: Fine-tune for Philippine news

### Phase 3 Features
1. **Multi-language Support**: Tagalog, Cebuano summaries
2. **Domain-specific Models**: Business, sports, politics
3. **Real-time Updates**: Live summary generation
4. **User Preferences**: Customizable summary styles

## 🎓 Thesis Integration

### Research Contributions
1. **Complete ML Pipeline**: Sentiment + Bias + Summarization
2. **Performance Analysis**: Processing time, memory usage
3. **User Experience**: Automated content understanding
4. **Real-world Application**: News aggregation with AI

### Evaluation Metrics
- **Processing Speed**: Articles per minute
- **Summary Quality**: ROUGE scores, human evaluation
- **User Engagement**: Time spent on articles with summaries
- **System Performance**: Memory usage, response times

## 🚨 Troubleshooting

### Common Issues

1. **Model Loading Errors**
   ```bash
   # Solution: Install transformers
   pip install transformers torch
   ```

2. **Memory Issues**
   ```bash
   # Solution: Use CPU-only mode
   export CUDA_VISIBLE_DEVICES=""
   ```

3. **Slow Processing**
   ```bash
   # Solution: Enable GPU acceleration
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

### Performance Tuning

1. **Model Optimization**
   ```python
   # Use smaller model for faster processing
   model_name = "facebook/bart-large-cnn"  # 1.6GB
   # Alternative: "facebook/bart-base"  # 500MB
   ```

2. **Batch Processing**
   ```python
   # Process multiple articles together
   def batch_summarize(articles):
       texts = [article['content'] for article in articles]
       summaries = summarizer(texts, max_length=150, min_length=30)
       return summaries
   ```

## 📚 References

- [Hugging Face Transformers](https://huggingface.co/transformers/)
- [BART Model Paper](https://arxiv.org/abs/1910.13461)
- [Text Summarization Best Practices](https://huggingface.co/docs/transformers/tasks/summarization)
- [PH-Eye Project Repository](https://github.com/your-repo/ph-eye)

## 📝 Implementation Checklist

- [ ] Create `backend/app/ml/summarization.py`
- [ ] Update `backend/requirements.txt`
- [ ] Update `backend/app/workers/ml_tasks.py`
- [ ] Add API endpoint in `backend/app/main.py`
- [ ] Update frontend article components
- [ ] Add summary fetching to `src/lib/articles.ts`
- [ ] Update Docker configuration
- [ ] Add environment variables
- [ ] Write unit tests
- [ ] Test with sample articles
- [ ] Monitor performance
- [ ] Document API endpoints
- [ ] Update project README

## 🎯 Success Criteria

- [ ] Summaries generated for 95%+ of articles
- [ ] Processing time < 5 seconds per article
- [ ] Memory usage < 3GB total
- [ ] User engagement increase with summaries
- [ ] No impact on existing functionality
- [ ] Clean, maintainable code
- [ ] Comprehensive documentation

---

**Implementation Time**: 2-3 hours for basic version, 4-6 hours for full features
**Maintenance**: Low (automated processing)
**Cost**: FREE (using Hugging Face models)
**Impact**: High (significant UX improvement)

*Last updated: January 2025*
*Version: 1.0*
