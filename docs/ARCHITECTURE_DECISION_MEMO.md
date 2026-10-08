# Architecture Decision Memo

**Maximum length: 500 words** (Word count: 432 words)

## Decision

I recommend shipping **Architecture A (Single-Agent with Deterministic Policy Engine)** for the initial production release.

While multi-agent patterns are popular, enterprise procurement triage is fundamentally a rule-driven classification problem with a small synthesis surface. Architecture A gives us full policy compliance, lower operating cost, and significantly lower latency without the orchestration fragility of Architecture B.

## Evidence

Both architectures were benchmarked against the identical 6-case public evaluation suite:

| Metric | Single-Agent (Architecture A) | Staged 2-Agent (Architecture B) | Notes |
|---|---:|---:|---|
| Public eval pass rate | 6 / 6 (100%) | 6 / 6 (100%) | Both satisfy all minimum policy checks |
| Average LLM calls / req | 1.0 | 2.0 | Architecture B doubles API consumption |
| Average tool calls / req | 6.0 | 5.0 | Both execute full evidence collection |
| Steady-state latency | ~2.5s – 12.0s | ~0.8s – 31.0s | Architecture A avoids multi-hop roundtrips |
| Policy grounding failures | 0 | 0 | Hard rules are enforced deterministically |
| Human authority preserved | Yes (Policy §11) | Yes (Policy §11) | Final purchase decision remains manual |

## Trade-offs

- **Latency & Reliability:** In Architecture B, each request requires two sequential LLM completions (Analyst brief -> Risk Reviewer synthesis). If either call encounters a network timeout, transient 503 spike, or rate limit, the entire pipeline is blocked. Architecture A keeps the external call surface to a single invocation.
- **Cost Efficiency:** Architecture B consumes roughly double the token count per request. At enterprise scale (thousands of software purchase requests per quarter), this adds unnecessary inference spend without providing any improvement in approval accuracy.
- **Explainability:** Architecture A evaluates all tools in Python and compiles verified evidence directly alongside the final recommendation. In Architecture B, Stage 2 relies on Stage 1's intermediate textual summary, introducing the risk of subtle information loss between agents.

## Risks / Limitations

1. **Third-Party Outages:** During vendor-risk API outages (`REQ-1009`), external security data cannot be retrieved. We mitigate this by failing closed: flagging `vendor_risk_unavailable` and routing to manual Security review.
2. **Adversarial Requester Input:** Untrusted text fields can contain prompt injections (`REQ-1006`). We strip and detect these patterns deterministically in Python before constructing prompts, treating business text strictly as data.
3. **Future Production Validation:** Before rollout across all enterprise business units, I would test with additional multi-year contract renewals and international subsidiary tax/currency conversions.

## Why this is the right MVP

In corporate procurement, mistakes carry financial and compliance liability. Math (budget comparisons), thresholds (approval tiers), and trigger rules (PII data access requiring privacy sign-off) must be 100% deterministic. Relying on an LLM to "reason" about dollar arithmetic or contract date math is an anti-pattern.

By handling all arithmetic, database lookups, and policy rules in deterministic Python and using a single LLM call solely to draft a concise, human-readable recommendation, Architecture A provides maximum reliability with the smallest possible failure surface.
