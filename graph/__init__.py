from .state import ChatState


def build_graph():
    """Lazy import and build graph to prevent circular imports."""
    from .workflow import build_graph as _bg

    return _bg()


def chat(message: str, chat_history=None, run_id=None):
    """Lazy import and execute chat graph turn."""
    from .workflow import chat as _chat

    return _chat(message, chat_history, run_id)


__all__ = ["ChatState", "build_graph", "chat"]
