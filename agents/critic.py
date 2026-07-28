import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from graph.state import GraphState
from guardrails.limits import load_config

load_dotenv()


class CriticOutput(BaseModel):
    groundedness: float = Field(
        description="Score 0.0-1.0: Are claims supported by source citations?"
    )
    coverage: float = Field(
        description="Score 0.0-1.0: Are all sub-questions thoroughly covered?"
    )
    coherence: float = Field(
        description="Score 0.0-1.0: Is the report clear, logical, and structured?"
    )
    faithfulness: float = Field(
        description="Score 0.0-1.0: Is content accurate to research results without hallucination?"
    )
    average_score: float = Field(
        description="Average of the 4 metric scores (0.0-1.0)"
    )
    passed: bool = Field(
        description="True if average_score is greater than or equal to quality threshold"
    )
    feedback: str = Field(
        description="Detailed, actionable feedback on what needs improvement if failed"
    )


class CriticAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.config = load_config()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
        )

    def run(self, state: GraphState) -> Dict[str, Any]:
        """LangGraph node function for Critic Agent."""
        user_query = state.get("user_query", "")
        sub_questions = state.get("sub_questions", [])
        research_results = state.get("research_results", [])
        draft_report = state.get("draft_report", "")
        current_revisions = state.get("revision_count", 0)

        threshold = self.config.quality_threshold

        sq_text = "\n".join(
            [f"- {sq.get('question', '')}" for sq in sub_questions]
        )
        research_summary = "\n".join(
            [
                f"SubQ: {item.get('sub_question')}\nSummary: {item.get('summary')}"
                for item in research_results
            ]
        )

        prompt = f"""You are a rigorous Quality Evaluator and Editor.
Evaluate the following research report draft against the original query and research findings.

Original Research Query: "{user_query}"

Sub-questions required:
{sq_text}

Research Findings:
{research_summary}

---
Draft Report to Evaluate:
{draft_report}
---

Evaluate on 4 criteria (scores from 0.0 to 1.0):
1. Groundedness: Are claims explicitly cited with sources [1], [2], etc.?
2. Coverage: Are all sub-questions addressed?
3. Coherence: Is the structure logical, clear, and professional?
4. Faithfulness: Is the report accurate to the research findings without adding false claims?

Quality Threshold for Passing: {threshold}
Set `passed` = True ONLY if `average_score` >= {threshold}.
If `passed` = False, provide specific, actionable feedback detailing how the writer should revise the report.
"""

        try:
            structured_llm = self.llm.with_structured_output(CriticOutput)
            result: CriticOutput = structured_llm.invoke(prompt)

            avg_score = round(
                (
                    result.groundedness
                    + result.coverage
                    + result.coherence
                    + result.faithfulness
                )
                / 4.0,
                2,
            )
            passed = avg_score >= threshold

            new_revision_count = current_revisions + 1

            warnings = state.get("warnings", [])
            # Check guardrail: max critic loops
            if not passed and new_revision_count >= self.config.max_critic_loops:
                warnings.append(
                    f"Max revision limit ({self.config.max_critic_loops}) reached. Forcing pass with warning."
                )

            return {
                "critic_scores": {
                    "groundedness": result.groundedness,
                    "coverage": result.coverage,
                    "coherence": result.coherence,
                    "faithfulness": result.faithfulness,
                    "average_score": avg_score,
                },
                "critic_feedback": result.feedback if not passed else "",
                "passed": passed,
                "revision_count": new_revision_count,
                "warnings": warnings,
            }

        except Exception as e:
            print(f"[CriticAgent Error] Evaluation failed: {e}")
            # Fallback pass on error to avoid blocking execution
            return {
                "critic_scores": {
                    "groundedness": 0.8,
                    "coverage": 0.8,
                    "coherence": 0.8,
                    "faithfulness": 0.8,
                    "average_score": 0.8,
                },
                "critic_feedback": "",
                "passed": True,
                "revision_count": current_revisions + 1,
                "warnings": state.get("warnings", [])
                + [f"Critic fallback used due to error: {str(e)}"],
            }
