import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from graph.state import GraphState
from guardrails.limits import load_config
from mcp_server.odoo_tools import query_customers, query_inventory, query_sales
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
            data_source = sq.get("data_source", "web")
            query_str = " ".join(keywords) if keywords else question_text

            tool_calls_used = 0
            sources: List[Dict[str, Any]] = []

            # 1. Execute Web Search if data_source is web or hybrid
            if data_source in ("web", "hybrid"):
                if tool_calls_used < self.config.max_tool_calls_per_subquestion:
                    tool_calls_used += 1
                    search_data = execute_web_search(query=query_str, max_results=3)
                    for item in search_data:
                        sources.append(
                            {
                                "url": item.get("url", ""),
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "source_type": "web",
                            }
                        )

            # 2. Execute ERP Queries if data_source is erp or hybrid
            if data_source in ("erp", "hybrid"):
                if tool_calls_used < self.config.max_tool_calls_per_subquestion:
                    tool_calls_used += 1
                    erp_sources = self._query_erp(question_text, keywords)
                    sources.extend(erp_sources)

            # Summarize findings from gathered sources
            summary = self._summarize_findings(question_text, sources)

            research_results.append(
                {
                    "sub_question": question_text,
                    "data_source": data_source,
                    "sources": sources,
                    "summary": summary,
                    "tool_calls_used": tool_calls_used,
                }
            )

        return {"research_results": research_results}

    def _query_erp(
        self, question: str, keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Analyze question & keywords to route to appropriate Odoo ERP queries."""
        erp_sources: List[Dict[str, Any]] = []
        kw_str = (question + " " + " ".join(keywords)).lower()

        # Check Sales / Revenue / Order
        if any(term in kw_str for term in ["sale", "revenue", "order", "doanh số", "bán hàng", "doanh thu"]):
            sales_json = query_sales(limit=10)
            erp_sources.append(
                {
                    "url": "odoo://sale.order",
                    "title": "Odoo ERP Sales & Orders Database",
                    "snippet": f"Sales Data: {sales_json}",
                    "source_type": "erp",
                }
            )

        # Check Inventory / Stock
        if any(term in kw_str for term in ["stock", "inventory", "quant", "tồn kho", "kho"]):
            inv_json = query_inventory(limit=10)
            erp_sources.append(
                {
                    "url": "odoo://stock.quant",
                    "title": "Odoo ERP Inventory Database",
                    "snippet": f"Inventory Data: {inv_json}",
                    "source_type": "erp",
                }
            )

        # Check Customers / Partners
        if any(term in kw_str for term in ["customer", "client", "partner", "khách hàng"]):
            cust_json = query_customers(limit=10)
            erp_sources.append(
                {
                    "url": "odoo://res.partner",
                    "title": "Odoo ERP Customers Database",
                    "snippet": f"Customer Accounts: {cust_json}",
                    "source_type": "erp",
                }
            )

        # Fallback to Sales if no specific ERP keyword matched
        if not erp_sources:
            sales_json = query_sales(limit=10)
            erp_sources.append(
                {
                    "url": "odoo://sale.order",
                    "title": "Odoo ERP Sales & Orders Database",
                    "snippet": f"Sales Data: {sales_json}",
                    "source_type": "erp",
                }
            )

        return erp_sources

    def _summarize_findings(
        self, question: str, sources: List[Dict[str, Any]]
    ) -> str:
        if not sources:
            return "No relevant sources found during research."

        sources_text_blocks = []
        for i, s in enumerate(sources):
            stype = s.get("source_type", "web").upper()
            sources_text_blocks.append(
                f"Source [{i+1}] ({stype}): {s['title']} ({s['url']})\nSnippet: {s['snippet']}"
            )

        sources_text = "\n\n".join(sources_text_blocks)

        prompt = f"""You are a meticulous Hybrid Research Assistant.
Summarize key findings to directly answer the sub-question below based on the provided sources (which include internal ERP data and/or web market research).
Include explicit source citations (e.g. [1], [2]). Clearly note internal ERP facts vs web market facts.

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
