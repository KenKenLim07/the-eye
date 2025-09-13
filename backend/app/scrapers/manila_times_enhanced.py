import time
import logging
import random
from typing import Optional, Dict, List
import httpx
from collections import defaultdict, deque
from datetime import datetime, timedelta

class EnhancedRetryMixin:
    """Enhanced retry logic with circuit breaker and user agent rotation."""
    
    def __init__(self):
        # Circuit breaker state
        self.failure_counts = defaultdict(int)
        self.last_failure_time = defaultdict(lambda: None)
        self.blocked_until = defaultdict(lambda: None)
        
        # Enhanced user agents for rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]
        self.ua_index = 0

    def _get_next_user_agent(self) -> str:
        """Rotate user agents on each request."""
        ua = self.user_agents[self.ua_index]
        self.ua_index = (self.ua_index + 1) % len(self.user_agents)
        return ua

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for circuit breaker."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return "unknown"

    def _is_circuit_open(self, domain: str) -> bool:
        """Check if circuit breaker is open for domain."""
        if self.blocked_until[domain] and datetime.now() < self.blocked_until[domain]:
            return True
        return False

    def _record_failure(self, domain: str):
        """Record failure and potentially open circuit."""
        self.failure_counts[domain] += 1
        self.last_failure_time[domain] = datetime.now()
        
        # Open circuit after 5 failures in short time
        if self.failure_counts[domain] >= 5:
            self.blocked_until[domain] = datetime.now() + timedelta(minutes=10)
            logging.warning(f"Circuit breaker opened for {domain} for 10 minutes")

    def _record_success(self, domain: str):
        """Record success and reset failure count."""
        self.failure_counts[domain] = 0
        self.blocked_until[domain] = None

    def _get_enhanced_headers(self, attempt: int = 0) -> Dict[str, str]:
        """Get headers with rotating user agent."""
        return {
            "User-Agent": self._get_next_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site"
        }

    def fetch_with_enhanced_retry(self, url: str, max_retries: int = 5) -> Optional[str]:
        """Enhanced fetch with circuit breaker, better retry logic, and user agent rotation."""
        domain = self._get_domain(url)
        
        # Check circuit breaker
        if self._is_circuit_open(domain):
            logging.warning(f"Circuit breaker open for {domain}, skipping {url}")
            return None

        retryable_status_codes = {429, 500, 502, 503, 504}
        
        for attempt in range(max_retries):
            try:
                # Dynamic timeout based on attempt
                timeout = min(30 + (attempt * 10), 60)
                
                # Enhanced headers with rotation
                headers = self._get_enhanced_headers(attempt)
                
                logging.info(f"Fetching {url} (attempt {attempt + 1}/{max_retries}) timeout={timeout}s UA={headers['User-Agent'][:50]}...")
                
                with httpx.Client(
                    follow_redirects=True,
                    timeout=float(timeout),
                    headers=headers,
                    verify=False
                ) as client:
                    response = client.get(url)
                    
                    # Handle different status codes
                    if response.status_code == 200:
                        self._record_success(domain)
                        return response.text
                    
                    elif response.status_code == 403:
                        logging.warning(f"403 Forbidden for {url} - might be blocked")
                        if attempt < max_retries - 1:
                            wait_time = random.uniform(60, 120)  # Longer wait for 403
                            logging.info(f"Waiting {wait_time:.1f}s before retry...")
                            time.sleep(wait_time)
                            continue
                        
                    elif response.status_code in retryable_status_codes:
                        if attempt < max_retries - 1:
                            # Exponential backoff with jitter
                            wait_time = (2 ** attempt) + random.uniform(1, 5)
                            logging.warning(f"{response.status_code} error for {url}, retrying in {wait_time:.1f}s")
                            time.sleep(wait_time)
                            continue
                    
                    else:
                        logging.error(f"Non-retryable {response.status_code} error for {url}")
                        self._record_failure(domain)
                        return None
                        
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(2, 8)
                    logging.warning(f"Timeout for {url}, retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"Final timeout for {url}")
                    self._record_failure(domain)
                    return None
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code in retryable_status_codes and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 5)
                    logging.warning(f"HTTP {e.response.status_code} for {url}, retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"HTTP error for {url}: {e.response.status_code}")
                    self._record_failure(domain)
                    return None
                    
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 5)
                    logging.warning(f"Request error for {url}, retrying in {wait_time:.1f}s: {str(e)[:100]}")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"Final request error for {url}: {str(e)[:100]}")
                    self._record_failure(domain)
                    return None
                    
            except Exception as e:
                logging.error(f"Unexpected error for {url}: {str(e)[:100]}")
                self._record_failure(domain)
                return None
        
        self._record_failure(domain)
        return None
