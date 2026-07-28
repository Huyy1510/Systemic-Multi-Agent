from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict):
    # Input
    user_query: str

    # Planner output
    sub_questions: List[Dict[str, Any]]

    # Researcher output
    research_results: List[Dict[str, Any]]

    # Writer output
    draft_report: str

    # Critic output
    critic_scores: Dict[str, float]  # groundedness, coverage, coherence, faithfulness
    critic_feedback: str
    passed: bool
    revision_count: int  # count of Writer <-> Critic loops

    # Meta
    final_report: str
    error: Optional[str]
    warnings: List[str]
