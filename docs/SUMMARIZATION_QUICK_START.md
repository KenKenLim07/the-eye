# 🚀 AI Summarization - Quick Start Guide

## ⚡ 30-Minute Implementation

This guide will get you up and running with AI summarization in 30 minutes.

## 🎯 What You'll Get

- ✅ Automatic article summaries
- ✅ Display in article cards
- ✅ Quick view modal integration
- ✅ Free forever (no API costs)
- ✅ Perfect for thesis demo

## 📋 Prerequisites

- ✅ PH-Eye system running
- ✅ Docker containers active
- ✅ 2GB+ free RAM
- ✅ Basic Python knowledge

## 🛠️ Step-by-Step Implementation

### Step 1: Add Dependencies (2 minutes)

```bash
# Add to backend/requirements.txt
echo "transformers==4.36.0" >> backend/requirements.txt
echo "torch==2.1.0" >> backend/requirements.txt
```

### Step 2: Create Summarization Module (10 minutes)

Create `backend/app/ml/summarization.py`:

```python
import time
from typing import Tuple, Dict, Any
import torch
from transformers import pipeline

_summarizer = None

def _ensure_summarizer():
    global _summarizer
    if _summarizer is not None:
        return _summarizer
    
    device = 0 if torch.cuda.is_available() else -1
    _summarizer = pipeline(
        "summarization",
        model="facebook/bart-large-cnn",
        device=device
    )
    return _summarizer

def analyze_text_summarization(text: str) -> Tuple[str, float, Dict[str, Any]]:
    start = time.time()
    
    if not text or len(text.strip()) < 50:
        return "", 0.0, {"error": "Text too short"}
    
    try:
        summarizer = _ensure_summarizer()
        clean_text = text.strip()[:4000]  # Truncate long text
        
        result = summarizer(
            clean_text,
            max_length=150,
            min_length=30,
            do_sample=False
        )
        
        summary = result[0]['summary_text'] if result else ""
        elapsed_ms = (time.time() - start) * 1000.0
        
        return summary, 0.8, {
            "processing_time_ms": int(elapsed_ms),
            "input_length": len(text),
            "output_length": len(summary)
        }
        
    except Exception as e:
        return "", 0.0, {"error": str(e)}

def build_summarization_row(article_id: int, text: str) -> Dict[str, Any]:
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
        "model_metadata": {**metadata, "summary": summary}
    }
```

### Step 3: Update ML Tasks (5 minutes)

Add to `backend/app/workers/ml_tasks.py`:

```python
from app.ml.summarization import build_summarization_row

def build_comprehensive_bias_analysis(article_id: int, text: str) -> list[Dict[str, Any]]:
    rows = []
    rows.append(build_bias_row_for_vader(article_id, text))
    rows.append(build_bias_row_for_philippine_political(article_id, text))
    
    # Add summarization
    rows.append(build_summarization_row(article_id, text))
    
    return rows
```

### Step 4: Add API Endpoint (5 minutes)

Add to `backend/app/main.py`:

```python
@app.get("/ml/summarization")
async def get_summarization(ids: str):
    try:
        article_ids = [int(id.strip()) for id in ids.split(",") if id.strip()]
    except ValueError:
        return {"error": "Invalid article IDs format"}
    
    sb = get_supabase()
    try:
        result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_type", "summarization").execute()
        return {"summaries": result.data or []}
    except Exception as e:
        return {"error": str(e)}
```

### Step 5: Update Frontend (8 minutes)

Update `src/components/articles/article-cards-interactive.tsx`:

```typescript
// Add summary to Article interface
interface Article {
  // ... existing fields
  summary?: string;
}

// In the component, add after sentiment badge:
{summary && (
  <div className="mt-2 p-2 bg-blue-50 rounded-md">
    <p className="text-xs text-blue-800 font-medium mb-1">Summary:</p>
    <p className="text-xs text-blue-700">{summary}</p>
  </div>
)}
```

Update `src/lib/articles.ts`:

```typescript
export async function fetchArticlesWithSummaries(articleIds: number[]) {
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/ml/summarization?ids=${articleIds.join(',')}`);
    if (response.ok) {
      const data = await response.json();
      const summaries: Record<number, string> = {};
      data.summaries?.forEach((item: any) => {
        const summary = item.model_metadata?.summary;
        if (summary) summaries[item.article_id] = summary;
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

### Restart Services

```bash
# Stop current services
./stop_ph_eye.sh

# Rebuild with new dependencies
docker-compose build

# Start services
./start_ph_eye.sh
```

### Test Implementation

```bash
# Test API endpoint
curl "http://localhost:8000/ml/summarization?ids=1,2,3"

# Check logs
tail -f backend/worker.log
```

## 🎯 Expected Results

After implementation, you should see:

1. **Article Cards**: Show summaries below sentiment badges
2. **Quick View Modal**: Display full summaries
3. **Processing**: New articles get summarized automatically
4. **Performance**: 2-5 seconds per article summary

## 🐛 Troubleshooting

### Model Loading Issues
```bash
# Check if transformers installed
docker exec ph-eye-worker python -c "import transformers; print('OK')"

# If error, rebuild container
docker-compose build --no-cache
```

### Memory Issues
```bash
# Check memory usage
docker stats

# If > 3GB, consider using smaller model
# Change model to "facebook/bart-base" in summarization.py
```

### No Summaries Showing
```bash
# Check if summaries are being generated
curl "http://localhost:8000/ml/summarization?ids=1"

# Check worker logs
docker logs ph-eye-worker | grep -i summary
```

## 📊 Performance Monitoring

### Check Processing Time
```bash
# Monitor worker logs
tail -f backend/worker.log | grep "processing_time_ms"
```

### Check Memory Usage
```bash
# Monitor container stats
docker stats --no-stream
```

## 🎓 Thesis Demo Script

1. **Show Article Cards**: "Here we can see articles with AI-generated summaries"
2. **Open Quick View**: "Clicking shows the full summary in context"
3. **Explain Processing**: "Summaries are generated automatically using BART model"
4. **Show Performance**: "Processing takes 2-5 seconds per article"
5. **Highlight Benefits**: "Users can quickly understand article content"

## 🚀 Next Steps

After basic implementation:

1. **Add Summary Length Options**: Short/medium/long
2. **Implement Caching**: Avoid reprocessing
3. **Add Quality Metrics**: Confidence scores
4. **Batch Processing**: Summarize existing articles
5. **User Preferences**: Customizable summary styles

## 📞 Support

If you encounter issues:

1. Check the full implementation guide: `docs/AI_SUMMARIZATION_IMPLEMENTATION.md`
2. Review Docker logs: `docker logs ph-eye-worker`
3. Test API endpoints: `curl http://localhost:8000/health`
4. Check memory usage: `docker stats`

---

**Total Implementation Time**: 30 minutes
**Difficulty Level**: Easy
**Prerequisites**: Basic Python, Docker knowledge
**Result**: Professional AI summarization feature

*Ready to implement? Start with Step 1!* 🚀
