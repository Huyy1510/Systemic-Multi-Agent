import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from graph.state import GraphState
from guardrails.limits import load_config
from mcp_server.search_tools import execute_web_search
from utils import clean_llm_text

load_dotenv()


class ResearcherAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.config = load_config()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.2,
        )

    def run(self, state: GraphState) -> Dict[str, Any]:
        """LangGraph node function for Researcher Agent."""
        sub_questions = state.get("sub_questions", [])
        if not sub_questions:
            return {"error": "No sub-questions provided for research", "research_results": []}

        research_results: List[Dict[str, Any]] = []

        for sq in sub_questions:
            question_text = sq.get("question", "")
            keywords = sq.get("search_keywords", [])
            query_str = " ".join(keywords) if keywords else question_text

            tool_calls_used = 0
            sources: List[Dict[str, str]] = []

            # Perform search tool call (capped by max_tool_calls_per_subquestion)
            if tool_calls_used < self.config.max_tool_calls_per_subquestion:
                tool_calls_used += 1
                search_data = execute_web_search(
                    query=query_str, max_results=3
                )
                for item in search_data:
                    sources.append(
                        {
                            "url": item.get("url", ""),
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                        }
                    )

            # Summarize gathered sources for this sub-question using LLM
            summary = self._summarize_findings(question_text, sources)

            research_results.append(
                {
                    "sub_question": question_text,
                    "sources": sources,
                    "summary": summary,
                    "tool_calls_used": tool_calls_used,
                }
            )

        return {"research_results": research_results}

    def _summarize_findings(
        self, question: str, sources: List[Dict[str, str]]
    ) -> str:
        if not sources:
            return "No relevant sources found during research."

        sources_text = "\n\n".join(
            [
                f"Source [{i+1}]: {s['title']} ({s['url']})\nSnippet: {s['snippet']}"
                for i, s in enumerate(sources)
            ]
        )

        prompt = f"""You are a meticulous Research Assistant.
Summarize key findings to directly answer the sub-question below based ONLY on the provided sources.
Include explicit source citations (e.g. [1], [2]).

Sub-question: "{question}"

Sources:
{sources_text}

Provide a concise, factual summary (2-3 paragraphs max):
"""
        try:
            response = self.llm.invoke(prompt)
            return clean_llm_text(response.content)
        except Exception as e:
            print(f"[ResearcherAgent Error] LLM summarization failed: {e}")
            return f"Summary unavailable (error: {e}). Raw snippets: " + "; ".join(
                [s["snippet"] for s in sources]
            )
