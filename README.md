# Mirsad (مرصاد)

**A runtime security firewall for AI agents.**

AI agents read emails, documents, and web pages, then act on them by calling tools. Any of that content can carry hidden instructions that hijack the agent into leaking data or taking unauthorized actions. This is prompt injection, the #1 risk in the OWASP Top 10 for LLM Applications.

Mirsad sits between an agent and its tools and checks every action before it runs:

- **Policy engine:** declarative per-tool and per-parameter rules
- **Taint tracking:** untrusted content can't push sensitive data outside
- **Injection detection:** scans tool outputs in Arabic and English
- **Human approval:** high-risk actions wait for sign-off on mobile
- **Audit log:** tamper-evident record of everything the agent did

Works with any LLM provider over MCP and function calling. No changes to the agent required.

> 🚧 Senior project in progress, Prince Sultan University, Fall 2026.
