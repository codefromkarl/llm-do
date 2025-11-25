from __future__ import annotations

import json
import os
import ssl
from typing import Dict, List
from urllib import parse, request

USER_AGENT = "llm-do-web-research/0.1"


def search_web(query: str, num_results: int = 5) -> List[Dict[str, str | None]]:
    """
    Run a lightweight web search.

    Prefers SerpAPI when SERPAPI_API_KEY is set; otherwise falls back to
    DuckDuckGo's JSON API. Returns a list of {url, title, snippet} dicts with
    duplicates removed.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    limit = max(1, min(num_results, 8))
    api_key = os.getenv("SERPAPI_API_KEY")

    if api_key:
        try:
            serpapi_hits = _search_serpapi(cleaned_query, api_key, limit)
            if serpapi_hits:
                return serpapi_hits[:limit]
        except Exception:
            # Fall back silently; the model can see the empty list if everything fails.
            pass

    try:
        return _search_duckduckgo(cleaned_query, limit)
    except Exception:
        return []


def _http_get_json(url: str, timeout: float = 12.0) -> dict:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    with request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    decoded = data.decode(charset, errors="replace")
    return json.loads(decoded)


def _search_serpapi(query: str, api_key: str, limit: int) -> List[Dict[str, str | None]]:
    url = (
        "https://serpapi.com/search.json?"
        f"engine=google&q={parse.quote(query)}&num={limit}&api_key={parse.quote(api_key)}"
    )
    payload = _http_get_json(url)
    results: List[Dict[str, str | None]] = []
    seen: set[str] = set()

    for item in payload.get("organic_results", []):
        link = item.get("link") or item.get("url")
        if not link or link in seen:
            continue
        seen.add(link)
        title = (item.get("title") or "").strip() or None
        snippet = (item.get("snippet") or item.get("rich_snippet", {}).get("top", {}).get("snippet"))
        results.append({"url": link, "title": title, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


def _search_duckduckgo(query: str, limit: int) -> List[Dict[str, str | None]]:
    url = (
        "https://api.duckduckgo.com/?"
        f"q={parse.quote(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    )
    payload = _http_get_json(url)
    results: List[Dict[str, str | None]] = []
    seen: set[str] = set()

    def _add_result(link: str | None, text: str | None) -> None:
        if not link or link in seen:
            return
        seen.add(link)
        snippet = (text or "").strip() or None
        results.append({"url": link, "title": None, "snippet": snippet})

    for item in payload.get("Results", []):
        _add_result(item.get("FirstURL"), item.get("Text"))
        if len(results) >= limit:
            return results

    for topic in payload.get("RelatedTopics", []):
        if "FirstURL" in topic:
            _add_result(topic.get("FirstURL"), topic.get("Text"))
        elif topic.get("Topics"):
            for sub in topic["Topics"]:
                _add_result(sub.get("FirstURL"), sub.get("Text"))
                if len(results) >= limit:
                    return results
        if len(results) >= limit:
            break

    return results[:limit]
