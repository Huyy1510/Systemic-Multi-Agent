import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from graph.state import GraphState
from utils import clean_llm_text

load_dotenv()


class WriterAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.3,
        )

    def run(self, state: GraphState) -> Dict[str, Any]:
        """LangGraph node function for Writer Agent."""
        user_query = state.get("user_query", "")
        research_results = state.get("research_results", [])
        critic_feedback = state.get("critic_feedback", "")

        if not research_results:
            return {
                "draft_report": f"# Research Report: {user_query}\n\n*No research results available.*"
            }

        # Build research summary text for prompt
        research_context_blocks: List[str] = []
        all_sources: List[Dict[str, Any]] = []

        source_counter = 1
        source_map: Dict[str, int] = {}

        for item in research_results:
            sq = item.get("sub_question", "")
            summary = item.get("summary", "")
            item_sources = item.get("sources", [])

            for s in item_sources:
                url = s.get("url", "")
                if url and url not in source_map:
                    source_map[url] = source_counter
                    all_sources.append(s)
                    source_counter += 1

            research_context_blocks.append(
                f"### Sub-question: {sq}\nFindings:\n{summary}\n"
            )

        research_context = "\n".join(research_context_blocks)
        
        references_blocks = []
        for i, s in enumerate(all_sources):
            stype = s.get("source_type", "web")
            if stype == "erp":
                references_blocks.append(f"[{i+1}] 🏢 **Internal ERP Data**: {s.get('title', s['url'])}")
            else:
                references_blocks.append(f"[{i+1}] 🌐 [{s.get('title', s['url'])}]({s['url']})")

        references_text = "\n".join(references_blocks)

        feedback_instruction = ""
        if critic_feedback:
            feedback_instruction = f"""
CRITICAL REVISION INSTRUCTION:
The previous draft received feedback from the reviewer. You MUST address these points:
"{critic_feedback}"
Improve the draft specifically to address this feedback while maintaining clean structure and citations.
"""

        prompt = f"""You are an Expert Hybrid Technical Writer and Business Analyst.
Synthesize the provided research findings (combining internal company ERP data and external web market research) into a comprehensive, professional Markdown report answering:
"{user_query}"

{feedback_instruction}

---
Research Findings:
{research_context}

Available Sources:
{references_text}
---

Report Structure Requirements:
1. # Title (descriptive and relevant)
2. ## Executive Summary (concise high-level synthesis contrasting internal performance vs external market trends)
3. ## Detailed Findings (structured under clear subheadings addressing sub-questions)
4. ## Strategic Recommendations & Key Takeaways
5. ## References & Data Sources (clearly list web links and internal ERP sources)

Guidelines:
- Some research findings come from internal company ERP databases (sales, inventory, customers), while others come from web search.
- Ensure all factual claims contain citations using [1], [2], etc. matching the reference list.
- Clearly distinguish between internal performance numbers and external market trends.
- Maintain an objective, executive-level professional tone.
- Output clean, valid Markdown format.
"""

        try:
            response = self.llm.invoke(prompt)
            draft_report = clean_llm_text(response.content)
            return {"draft_report": draft_report}
        except Exception as e:
            print(f"[WriterAgent Error] LLM generation failed: {e}")
            fallback_report = f"# Research Report: {user_query}\n\n## Executive Summary\nError generating report: {e}\n\n## Research Findings\n{research_context}\n\n## References\n{references_text}"
            return {"draft_report": fallback_report}
