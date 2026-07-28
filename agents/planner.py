import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from graph.state import GraphState
from guardrails.limits import load_config

load_dotenv()


class SubQuestion(BaseModel):
    question: str = Field(description="Specific sub-question to research")
    priority: int = Field(description="Priority (1=highest, 5=lowest)")
    search_keywords: List[str] = Field(description="List of relevant search keywords")


class PlannerOutput(BaseModel):
    sub_questions: List[SubQuestion] = Field(
        description="3 to 5 sub-questions prioritizing key aspects"
    )
    reasoning: str = Field(description="Rationale for the sub-question breakdown")


class PlannerAgent:
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
        """LangGraph node function for Planner Agent."""
        user_query = state.get("user_query", "")
        if not user_query:
            return {"error": "User query is empty", "sub_questions": []}

        prompt = f"""You are an elite Research Planner.
Analyze the following research query and break it down into 3 to 5 clear, searchable sub-questions.
Query: "{user_query}"

Provide priority (1-5, where 1 is highest priority) and effective search keywords for each sub-question.
Ensure the total number of sub-questions does not exceed {self.config.max_sub_questions}.
"""

        try:
            structured_llm = self.llm.with_structured_output(PlannerOutput)
            result: PlannerOutput = structured_llm.invoke(prompt)

            sub_qs = result.sub_questions
            # Sort by priority and cap at max_sub_questions
            sub_qs = sorted(sub_qs, key=lambda x: x.priority)[
                : self.config.max_sub_questions
            ]

            formatted_sub_qs = [sq.model_dump() for sq in sub_qs]
            return {
                "sub_questions": formatted_sub_qs,
                "warnings": (
                    state.get("warnings", [])
                    + (
                        [
                            f"Capped sub-questions to max limit of {self.config.max_sub_questions}."
                        ]
                        if len(result.sub_questions) > self.config.max_sub_questions
                        else []
                    )
                ),
            }
        except Exception as e:
            print(f"[PlannerAgent Error] {e}")
            # Fallback if structured output fails
            fallback_sub_qs = [
                {
                    "question": user_query,
                    "priority": 1,
                    "search_keywords": user_query.split(),
                }
            ]
            return {
                "sub_questions": fallback_sub_qs,
                "error": f"Planner structured output fallback used due to: {str(e)}",
            }
