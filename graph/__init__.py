from .state import GraphState


def build_graph():
    """Lazy import and build graph to prevent circular imports."""
    from .workflow import build_graph as _bg

    return _bg()


def run_research(query: str, run_id=None):
    """Lazy import and run research to prevent circular imports."""
    from .workflow import run_research as _rr

    return _rr(query, run_id)


__all__ = ["GraphState", "build_graph", "run_research"]
