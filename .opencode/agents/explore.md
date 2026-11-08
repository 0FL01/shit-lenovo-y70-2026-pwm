---
description: Fast agent specialized for exploring codebases. Use this when you need to quickly find files by patterns (eg. "src/components//.tsx"), search code for keywords (eg. "API endpoints"), or answer questions about the codebase (eg. "how do API endpoints work?"). When calling this agent, specify the desired thoroughness level: "quick" for basic searches, "medium" for moderate exploration, or "very thorough" for comprehensive analysis across multiple locations and naming conventions.
mode: subagent
#model: arbuz/cx/gpt-5.5-xhigh
#model: ludka2/cx/gpt-6.1-terra
model: ludka2/ocg/deepseek-v4.1-flash
#model: ludka2/cx/gpt-6-luna-fast
#model: zai-coding-plan/glm-5.2
#model: fireworks-ai/accounts/fireworks/models/glm-5p2
#model: opencode-go/mimo-v2.5
#model: opencode-go/deepseek-v4-flash
variant: max
permissions:
  - action: github_actions_list
    resource: "*"
    effect: allow
  - action: github_actions_get
    resource: "*"
    effect: allow
  - action: github_actions_write
    resource: "*"
    effect: deny
  - action: edit
    resource: "*"
    effect: deny
  - action: edit
    resource: "*"
    effect: deny
  - action: read
    resource: "*"
    effect: allow
  - action: read
    resource: "~/.ssh/*"
    effect: deny
  - action: read
    resource: "*/.ssh/*"
    effect: deny
  - action: read
    resource: "~/.ssh*"
    effect: deny
  - action: read
    resource: "~/.config/opencode/secrets.env"
    effect: deny
  - action: read
    resource: "/tmp"
    effect: deny
  - action: read
    resource: "/tmp/"
    effect: deny
  - action: read
    resource: "/tmp/*"
    effect: deny
  - action: read
    resource: "/tmp/**"
    effect: deny
  - action: read
    resource: "*/tmp*"
    effect: deny
  - action: read
    resource: "*/tmp/**"
    effect: deny
  - action: tavily-local_*
    resource: "*"
    effect: allow
  - action: codex_web_search
    resource: "*"
    effect: allow
  - action: execute
    resource: "*"
    effect: allow
  - action: websearch
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: allow
  - action: shell
    resource: "*~/.ssh*"
    effect: deny
  - action: shell
    resource: "*$HOME/.ssh*"
    effect: deny
  - action: shell
    resource: "*/.ssh/*"
    effect: deny
  - action: shell
    resource: "/tmp"
    effect: deny
  - action: shell
    resource: "/tmp/"
    effect: deny
  - action: shell
    resource: "/tmp/*"
    effect: deny
  - action: shell
    resource: "/tmp/**"
    effect: deny
  - action: shell
    resource: "*/tmp*"
    effect: deny
  - action: shell
    resource: "*/tmp/**"
    effect: deny
  - action: external_directory
    resource: "*"
    effect: allow
  - action: external_directory
    resource: "~/.ssh*"
    effect: deny
  - action: external_directory
    resource: "~/.ssh/**"
    effect: deny
  - action: external_directory
    resource: "~/.config/opencode/secrets.env"
    effect: deny
  - action: external_directory
    resource: "/tmp"
    effect: deny
  - action: external_directory
    resource: "/tmp/"
    effect: deny
  - action: external_directory
    resource: "/tmp/*"
    effect: deny
  - action: external_directory
    resource: "/tmp/**"
    effect: deny
---
You explore codebases. Be fast and precise.

Tools:
- glob — fallback file discovery by pattern
- grep — fallback text search for strings, TODOs, or configs
- read — load file content in small chunks only when needed
- shell — fallback for terminal operations
- execute with `tools.codex_web.search` — indexed public web search and research
- webfetch — fetch a known URL

Rules:
1. Start with the smallest useful search.
2. Choose one discovery tool by intent: `glob`, `grep`, or `read`.
3. Use `read` only for small targeted chunks.
4. Return absolute paths and line numbers.
5. No emojis. No advice. Just facts.
6. Use only Codex MCP for web search. If it is unavailable or fails, report the error; do not fall back to built-in `websearch` or other search providers.
