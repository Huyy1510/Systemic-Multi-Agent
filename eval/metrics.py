from typing import Any, Dict, List


def calculate_chat_metrics(eval_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate chatbot evaluation metrics over benchmark test runs."""
    total_runs = len(eval_results)
    if total_runs == 0:
        return {
            "total_runs": 0,
            "intent_accuracy": 0.0,
            "guardrail_effectiveness": 0.0,
            "passed_scenarios": 0,
            "avg_latency_ms": 0.0,
        }

    correct_intents = sum(1 for r in eval_results if r.get("intent_match", False))
    intent_accuracy = round((correct_intents / total_runs) * 100, 2)

    off_topic_runs = [r for r in eval_results if r.get("expected_intent") == "off_topic"]
    if off_topic_runs:
        blocked_count = sum(1 for r in off_topic_runs if r.get("intent_match", False))
        guardrail_effectiveness = round((blocked_count / len(off_topic_runs)) * 100, 2)
    else:
        guardrail_effectiveness = 100.0

    passed_scenarios = sum(1 for r in eval_results if r.get("passed", False))
    avg_latency = round(sum(r.get("latency_ms", 0) for r in eval_results) / total_runs, 1)

    return {
        "total_runs": total_runs,
        "intent_accuracy": intent_accuracy,
        "guardrail_effectiveness": guardrail_effectiveness,
        "passed_scenarios": passed_scenarios,
        "avg_latency_ms": avg_latency,
    }


def generate_chat_report(metrics: Dict[str, Any], eval_results: List[Dict[str, Any]]) -> str:
    """Generate Markdown report summarizing Chatbot Benchmark Evaluation results."""
    md = []
    md.append("# 📊 ERP Sales Chatbot Benchmark Report\n")
    md.append("### Summary Metrics\n")
    md.append(f"- **Total Test Scenarios**: `{metrics['total_runs']}`")
    md.append(f"- **Intent Accuracy Rate**: `{metrics['intent_accuracy']}%` (Target ≥ 85%)")
    md.append(f"- **Guardrail Effectiveness**: `{metrics['guardrail_effectiveness']}%` (Off-topic blocking)")
    md.append(f"- **Average Turn Latency**: `{metrics['avg_latency_ms']} ms`")
    md.append(f"- **Passed Scenarios**: `{metrics['passed_scenarios']} / {metrics['total_runs']}`\n")

    md.append("### Scenario Results Breakdown\n")
    md.append("| ID | User Message | Expected Intent | Detected Intent | Status | Latency |")
    md.append("|---|---|---|---|---|---|")

    for r in eval_results:
        status_icon = "PASS ✅" if r.get("intent_match") else "FAIL ❌"
        msg_snippet = (r['message'][:35] + "..") if len(r['message']) > 35 else r['message']
        md.append(
            f"| `{r['id']}` | {msg_snippet} | `{r['expected_intent']}` | `{r['detected_intent']}` | {status_icon} | {r['latency_ms']}ms |"
        )

    return "\n".join(md)
