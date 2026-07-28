import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class GuardrailConfig:
    max_critic_loops: int = 3
    max_tool_calls_per_subquestion: int = 3
    tool_call_timeout_seconds: int = 15
    max_sub_questions: int = 5
    quality_threshold: float = 0.75
    max_tokens_per_request: int = 8000


def load_config() -> GuardrailConfig:
    """Load configuration from environment variables with fallback to defaults."""
    return GuardrailConfig(
        max_critic_loops=int(os.getenv("MAX_CRITIC_LOOPS", "3")),
        max_tool_calls_per_subquestion=int(
            os.getenv("MAX_TOOL_CALLS_PER_SUBQUESTION", "3")
        ),
        tool_call_timeout_seconds=int(os.getenv("TOOL_CALL_TIMEOUT", "15")),
        max_sub_questions=int(os.getenv("MAX_SUB_QUESTIONS", "5")),
        quality_threshold=float(os.getenv("QUALITY_THRESHOLD", "0.75")),
        max_tokens_per_request=int(os.getenv("MAX_TOKENS_PER_REQUEST", "8000")),
    )
