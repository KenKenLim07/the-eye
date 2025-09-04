# 🕵️ BLACK HAT RECONNAISSANCE METHODOLOGY
## Advanced Website Structure Analysis & Scraping Intelligence

> **⚠️ DISCLAIMER**: This methodology is for educational and legitimate research purposes only. Always respect robots.txt, rate limits, and terms of service.

---

## 🎯 MISSION OBJECTIVE
Develop a systematic approach to understand website architecture before implementing any scraping solution. Think like a penetration tester - reconnaissance first, exploitation second.

---

## 🔍 THE BLACK HAT MINDSET

### Core Principles:
1. **Reconnaissance is King** - Never attack what you don't understand
2. **Multiple Attack Vectors** - Always have backup plans
3. **Stealth & Persistence** - Avoid detection, maintain access
4. **Document Everything** - Knowledge is power
5. **Adapt & Overcome** - Every target is different

---

## 📋 RECONNAISSANCE PHASES

### Phase 1: Target Identification
```bash
# Basic footprinting
curl -s "https://TARGET_DOMAIN" | head -20
curl -s "https://TARGET_DOMAIN" | grep -E 'href="[^"]*TARGET_DOMAIN[^"]*"' | head -10
```

**What to look for:**
- Technology stack indicators
- Content management system
- JavaScript frameworks
- API endpoints in source code

### Phase 2: Feed Discovery
```bash
# Standard RSS/XML endpoints
curl -s "https://TARGET_DOMAIN/feed/" | head -20
curl -s "https://TARGET_DOMAIN/rss.xml" | head -20
curl -s "https://TARGET_DOMAIN/feed.xml" | head -20
```

**Why this matters:**
- RSS feeds are often the easiest entry point
- Usually contain structured data
- Less likely to have anti-bot protection
- Can reveal API patterns

### Phase 3: API Endpoint Mapping
```bash
# Search for API references
curl -s "https://TARGET_DOMAIN" | grep -i "api\|rss\|feed\|xml" | head -10

# Common API patterns
curl -s "https://TARGET_DOMAIN/api/v1/collections/home.rss"
curl -s "https://TARGET_DOMAIN/api/v1/posts.rss"
curl -s "https://TARGET_DOMAIN/api/feed"
```

**Intelligence gathering:**
- API versioning patterns
- Endpoint naming conventions
- Authentication requirements
- Rate limiting behavior

### Phase 4: Content Structure Analysis
```bash
# Extract structured data
curl -s "https://TARGET_DOMAIN/api/v1/collections/home.rss" | grep -E "<title>|<link>" | head -20
curl -s "https://TARGET_DOMAIN/api/v1/collections/home.rss" | sed -n 's/<title>\(.*\)<\/title>/\1/p' | head -10
```

**Data extraction patterns:**
- Title extraction
- Link extraction
- Date parsing
- Category identification

### Phase 5: Advanced Reconnaissance
```bash
# Sitemap analysis
curl -s "https://TARGET_DOMAIN/sitemap.xml" | head -20
curl -s "https://TARGET_DOMAIN/robots.txt"

# Alternative data formats
curl -s "https://TARGET_DOMAIN/api/v1/posts.json" | head -20
curl -s "https://TARGET_DOMAIN/graphql" | head -20
```

**Advanced techniques:**
- Sitemap crawling
- Robots.txt analysis
- JSON API discovery
- GraphQL endpoint detection

---

## 🛠️ TOOLS & TECHNIQUES

### Command Line Arsenal:
- `curl` - HTTP requests and data extraction
- `grep` - Pattern matching and filtering
- `sed` - Text processing and transformation
- `awk` - Advanced text processing
- `head/tail` - Output limiting
- `wc` - Word/line counting

### Advanced Techniques:
```bash
# Rate limit testing
for i in {1..10}; do curl -s "https://TARGET_DOMAIN/api/endpoint" | wc -l; sleep 1; done

# Authentication testing
curl -s "https://TARGET_DOMAIN/api/endpoint" | grep -i "auth\|login\|token"

# Data extraction patterns
curl -s "https://TARGET_DOMAIN/api/endpoint" | sed -n 's/<title>\(.*\)<\/title>/\1/p'
```

---

## 📊 INTELLIGENCE ANALYSIS

### What to Document:
1. **API Endpoints** - All discovered endpoints and their purposes
2. **Data Formats** - RSS, JSON, XML, HTML structures
3. **Rate Limits** - Request frequency restrictions
4. **Authentication** - Required headers, tokens, cookies
5. **Content Patterns** - How data is structured and organized
6. **Error Handling** - What happens when requests fail

### Target Classification:
- **Easy Targets** - Open RSS feeds, no rate limits
- **Medium Targets** - API with rate limits, some protection
- **Hard Targets** - Heavy anti-bot protection, authentication required
- **Impossible Targets** - Cloudflare protection, CAPTCHA, etc.

---

## 🎭 OPERATIONAL SECURITY

### Stealth Techniques:
- Use realistic User-Agent strings
- Implement random delays between requests
- Rotate IP addresses if possible
- Respect robots.txt directives
- Monitor for rate limiting responses

### Detection Avoidance:
```bash
# Realistic User-Agent
curl -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" "https://TARGET_DOMAIN"

# Random delays
sleep $((RANDOM % 5 + 1))
```

---

## 📈 SUCCESS METRICS

### Reconnaissance Success:
- ✅ Discovered working RSS/API endpoints
- ✅ Identified data structure patterns
- ✅ Mapped rate limiting behavior
- ✅ Documented authentication requirements
- ✅ Created extraction patterns

### Implementation Readiness:
- ✅ Can extract titles, links, dates
- ✅ Understands pagination patterns
- ✅ Knows rate limit thresholds
- ✅ Has fallback extraction methods
- ✅ Can handle errors gracefully

---

## 🚀 NEXT STEPS

After successful reconnaissance:

1. **Build Extraction Scripts** - Use discovered patterns
2. **Implement Rate Limiting** - Respect discovered limits
3. **Add Error Handling** - Handle edge cases
4. **Test Thoroughly** - Validate all extraction methods
5. **Monitor Performance** - Track success rates
6. **Maintain Stealth** - Avoid detection

---

## 📚 CASE STUDIES

### Successful Reconnaissance Examples:
- **Rappler.com** - Standard RSS feed discovery
- **Sunstar.com.ph** - API endpoint mapping
- **News sites** - Multiple feed formats

### Lessons Learned:
- Always check multiple feed formats
- API endpoints often more reliable than HTML scraping
- Rate limiting varies significantly between sites
- Some sites have hidden API endpoints

---

## ⚖️ LEGAL & ETHICAL CONSIDERATIONS

### Always:
- Respect robots.txt
- Implement reasonable rate limits
- Use data responsibly
- Follow terms of service
- Consider site owner's resources

### Never:
- Overwhelm servers with requests
- Scrape personal/sensitive data
- Violate terms of service
- Use data for malicious purposes
- Ignore rate limiting responses

---

## 🔧 QUICK REFERENCE

### Essential Commands:
```bash
# Basic recon
curl -s "https://TARGET_DOMAIN" | head -20

# Feed discovery
curl -s "https://TARGET_DOMAIN/feed/" | head -20

# API discovery
curl -s "https://TARGET_DOMAIN" | grep -i "api"

# Data extraction
curl -s "https://TARGET_DOMAIN/api/endpoint" | sed -n 's/<title>\(.*\)<\/title>/\1/p'
```

### Common Patterns:
- RSS: `/feed/`, `/rss/`, `/rss.xml`
- API: `/api/v1/`, `/api/`, `/v1/`
- JSON: `.json` extension
- Sitemap: `/sitemap.xml`

---

**Remember: The best scraper is the one that never gets detected. Reconnaissance is your weapon.**
