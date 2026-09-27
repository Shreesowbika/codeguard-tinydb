# CodeGuard: One-Scan Multi-Lens Modernization

**IBM Bob 2.0 Hackathon Submission**

**Team:** HackPulse
**Team Lead:** SRISHANTH S
**Member:** SHREE SOWBIKA S Y

---

## 🧠 IBM Bob Usage & Architecture

Most modernization tools re-scan the codebase separately for each concern, wasting time and token limits. CodeGuard leverages IBM Bob's advanced orchestration:
* **Document Understanding (The Main Agent):** Ingests the repository once to build a condensed structural map, bypassing the massive token cost of re-ingesting raw code for every task.
* **Parallel Subagents (Lens A & Lens B):** Using the shared context map, Bob spawned two parallel subagents. Lens A hunted for structural matches to known historical cache-mutation bugs, while Lens B simultaneously mapped dead/unreachable code.

## 🛡️ The CodeGuard Safety Gate (Catching an AI Hallucination)

AI agents are often reckless, hallucinating fixes that break undocumented design contracts. CodeGuard is built for enterprise safety, prioritizing 100% test integrity over inflated metrics.

During our scan of the TinyDB repository, the parallel subagents flagged 14 potential issues. CodeGuard's Safety Gate handled them as follows:

1. **Blocked Dead-Code Deletions (Lens B):** The AI flagged 6 unused symbols (like `mypy_plugin.py`). A naive tool would have deleted them. CodeGuard recognized they were dynamically referenced config files and blocked the deletion, moving them to manual review.
2. **Caught a Breaking AI Hallucination (Lens A):** Bob generated a `copy.deepcopy` fix for the `Table.search` cache. However, when we ran CodeGuard's automated regression check, it broke `test_query_cache_documents_are_shared_with_cache`. We discovered TinyDB's maintainers *intentionally* share this cache memory as a performance tradeoff. CodeGuard caught the AI breaking an undocumented design contract, automatically rejected the fix, and flagged it for maintainer awareness.

## 🚀 Measurable Impact
The breaking changes were safely reverted, and CodeGuard surgically shipped the remaining verified fixes. 

* **4 Critical Memory-Leak Vulnerabilities Patched** in the Storage and Middleware layers.
* **100% Test Integrity Maintained:** 231 tests passed, 0 regressions.
* **Hours to Minutes:** What would take a senior developer hours of manual auditing and testing was completed in minutes using Bob's parallelized subagent workflow.

## 📊 Data & Compliance
This prototype was executed against `msiemens/tinydb`, a publicly available, open-source Python document database operating under the commercial-use-friendly MIT License. All data compliance requirements for the hackathon are met.

## 📂 Deliverables
* `/bob_sessions`: Contains the required IBM Bob UI session consumption screenshots proving parallel subagent execution.
* `/tests/test_cache_mutation_regression.py`: Contains the AI-generated regression tests to prevent future cache leaks.
