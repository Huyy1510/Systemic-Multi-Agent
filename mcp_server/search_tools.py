import os
import re
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()


def execute_web_search(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Execute web search with Tavily primary and DuckDuckGo fallback."""
    results: List[Dict[str, Any]] = []

    # 1. Try Tavily
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key and tavily_key != "your_tavily_api_key_here":
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=tavily_key)
            response = client.search(query=query, max_results=max_results)
            for item in response.get("results", []):
                results.append(
                    {
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("content", ""),
                    }
                )
            if results:
                return results
        except Exception as e:
            print(f"[MCP Search Warning] Tavily search failed: {e}. Falling back to DuckDuckGo.")

    # 2. Fallback to DuckDuckGo
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            ddg_results = list(ddgs.text(query, max_results=max_results))
            for item in ddg_results:
                results.append(
                    {
                        "url": item.get("href", item.get("url", "")),
                        "title": item.get("title", ""),
                        "snippet": item.get("body", item.get("snippet", "")),
                    }
                )
    except Exception as e:
        print(f"[MCP Search Error] DuckDuckGo search failed: {e}")

    return results


def execute_web_fetch(url: str) -> str:
    """Fetch URL content using httpx and return cleaned plain text (max 3000 chars)."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text

            # Strip script and style elements
            cleaned_html = re.sub(
                r"<(script|style)[^>]*>.*?</\1>",
                "",
                html_content,
                flags=re.DOTALL | re.IGNORECASE,
            )
            # Strip remaining HTML tags
            plain_text = re.sub(r"<[^>]+>", " ", cleaned_html)
            # Collapse multiple whitespaces
            plain_text = re.sub(r"\s+", " ", plain_text).strip()

            return plain_text[:3000]
    except Exception as e:
        return f"Error fetching URL {url}: {str(e)}"


# FastMCP Server definition for stdio transport
try:
    from mcp.server.fastmcp import FastMCP

    mcp_app = FastMCP("SearchTools")

    @mcp_app.tool()
    def web_search(query: str, max_results: int = 3) -> str:
        """Search the web for information given a search query."""
        import json

        results = execute_web_search(query, max_results)
        return json.dumps(results, ensure_ascii=False)

    @mcp_app.tool()
    def web_fetch(url: str) -> str:
        """Fetch and extract readable plain text from a web URL."""
        return execute_web_fetch(url)

except ImportError:
    mcp_app = None


if __name__ == "__main__":
    if mcp_app:
        mcp_app.run(transport="stdio")
    else:
        print("mcp package standard server runner not configured.")
