# 📊 ERP Sales Chatbot Benchmark Report

### Summary Metrics

- **Total Test Scenarios**: `3`
- **Intent Accuracy Rate**: `100.0%` (Target ≥ 85%)
- **Guardrail Effectiveness**: `100.0%` (Off-topic blocking)
- **Average Turn Latency**: `35710.0 ms`
- **Passed Scenarios**: `3 / 3`

### Scenario Results Breakdown

| ID | User Message | Expected Intent | Detected Intent | Status | Latency |
|---|---|---|---|---|---|
| `c01` | Tư vấn cho tôi laptop tầm 20 triệu .. | `product_inquiry` | `product_inquiry` | PASS ✅ | 47140ms |
| `c02` | Bên bạn có những loại smartphone nà.. | `product_inquiry` | `product_inquiry` | PASS ✅ | 46182ms |
| `c03` | What laptops do you recommend for g.. | `product_inquiry` | `product_inquiry` | PASS ✅ | 13808ms |