from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse

import requests

# Core API endpoints (these are the correct ones for MMA)
CORE_ATHLETES_URL = (
    "http://sports.core.api.espn.com/v2/sports/mma/leagues/ufc/athletes"
)
CORE_ATHLETE_DETAIL_URL = (
    "http://sports.core.api.espn.com/v2/sports/mma/athletes/{id}"
)
CORE_ATHLETE_EVENTLOG_URL = (
    "http://sports.core.api.espn.com/v2/sports/mma/athletes/{id}/eventlog"
)


class ESPNApiClient:
    def __init__(
        self,
        cache_dir: str,
        rate_limit_seconds: float = 0.5,
        user_agent: str = "MMA-ELO-Collector/0.1",
        timeout_seconds: int = 30,
    ) -> None:
        self.cache_dir = cache_dir
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, url: str, params: Optional[Dict[str, Any]]) -> str:
        encoded = urlencode(sorted((params or {}).items()), doseq=True)
        key = f"{url}?{encoded}" if encoded else url
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _cache_path(self, url: str, params: Optional[Dict[str, Any]]) -> str:
        return os.path.join(self.cache_dir, f"{self._cache_key(url, params)}.json")

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)

    def get_json(
        self, url: str, params: Optional[Dict[str, Any]] = None, ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        cache_path = self._cache_path(url, params)
        if os.path.exists(cache_path):
            if ttl_seconds is None:
                with open(cache_path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            age = time.time() - os.path.getmtime(cache_path)
            if age <= ttl_seconds:
                with open(cache_path, "r", encoding="utf-8") as handle:
                    return json.load(handle)

        self._rate_limit()
        response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self._last_request_ts = time.time()
        return payload

    def get_all_athletes(self, limit: int = 1000) -> List[Tuple[str, str]]:
        """
        Fetch all UFC athletes. Returns list of (athlete_id, name) tuples.
        
        Uses pagination to fetch all athletes. Continues until no more items are returned.
        Deduplicates athlete IDs to handle any API pagination issues.
        """
        athletes: List[Tuple[str, str]] = []
        page_index = 1  # ESPN API uses 1-based page indexing (pageIndex starts at 1)
        total = None
        total_pages = None

        while True:
            # Use pageIndex instead of offset for pagination
            params = {"limit": limit, "pageIndex": page_index}
            payload = self.get_json(CORE_ATHLETES_URL, params=params)
            items = payload.get("items") or []
            
            # If no items returned, we're done
            if not items:
                break

            # Update metadata from first page
            if total is None:
                total = payload.get("count")
            if total_pages is None:
                total_pages = payload.get("pageCount")
            
            # Process items
            for item in items:
                athlete_id = self._extract_id_from_ref(item)
                if athlete_id:
                    athletes.append((athlete_id, ""))  # Name fetched separately

            print(f"  Fetched {len(athletes)} / {total or '?'} athletes... (page {page_index}/{total_pages or '?'}, items this page: {len(items)})")
            
            # Stop if we've fetched all pages
            if total_pages is not None and page_index >= total_pages:
                break
            
            # Stop if we got fewer items than requested (last page reached)
            if len(items) < limit:
                break
            
            # Increment page index for next iteration
            page_index += 1
            
            # Safety check to avoid infinite loop
            if page_index > 100:
                print(f"  Safety limit reached (100 pages), stopping")
                break

        return athletes

    def get_athlete_detail(self, athlete_id: str) -> Dict[str, Any]:
        """Get athlete profile details (name, etc.)."""
        return self.get_json(CORE_ATHLETE_DETAIL_URL.format(id=athlete_id))

    def get_athlete_eventlog(self, athlete_id: str) -> Dict[str, Any]:
        """Get athlete's fight history (event log)."""
        return self.get_json(CORE_ATHLETE_EVENTLOG_URL.format(id=athlete_id))

    def get_event_detail(self, event_url: str) -> Dict[str, Any]:
        """Fetch event details from a $ref URL."""
        return self.get_json(event_url)

    def get_competition_detail(self, competition_url: str) -> Dict[str, Any]:
        """Fetch competition details from a $ref URL."""
        return self.get_json(competition_url)

    def get_competition_status(self, competition_url: str) -> Dict[str, Any]:
        """Fetch competition status (result/method) from a competition URL."""
        status_url = competition_url.rstrip("/") + "/status"
        # Handle query params
        if "?" in competition_url:
            base, params = competition_url.split("?", 1)
            status_url = base.rstrip("/") + "/status?" + params
        return self.get_json(status_url)

    def _extract_id_from_ref(self, item: Any) -> Optional[str]:
        """Extract athlete ID from a $ref URL or dict."""
        if isinstance(item, str):
            return self._id_from_url(item)
        if isinstance(item, dict):
            ref = item.get("$ref")
            if ref:
                return self._id_from_url(ref)
            if "id" in item:
                return str(item["id"])
        return None

    def _id_from_url(self, url: str) -> Optional[str]:
        """Extract the last path segment (ID) from a URL."""
        parsed = urlparse(url)
        if parsed.path:
            # Remove query params and get last segment
            path = parsed.path.rstrip("/")
            return path.split("/")[-1]
        return None
