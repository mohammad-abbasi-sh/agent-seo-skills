# agent-seo-skills

[🇮🇷 توضیحات فارسی](README-fa.md)

**Give your AI agent SEO hands.** A growing pack of [Agent Skills](https://agentskills.io) + an MCP server that turn Claude Code, Claude Desktop, Cursor, Codex and other agents into an SEO operator — local-first, zero API keys, zero dependencies (Python standard library only).

Most SEO-for-agents tools need paid API keys or OAuth connections. This pack works on any public URL, offline-friendly, with deterministic scripts your agent runs and reads — no invented metrics, ever.

## What's inside (v0.2)

| Piece | What it does |
|---|---|
| `skills/site-audit` | Agent Skill: audit any page (title, meta, H1, canonical, robots, OG, JSON-LD, images/alt, links, word count) → 0–100 score + prioritized fixes |
| `skills/striking-distance` | Agent Skill: analyze a Search Console CSV export — striking-distance queries (positions 8–20), CTR opportunities vs position peers, keyword cannibalization |
| `mcp-server/` | Zero-dependency MCP server exposing the same audit engine as an `audit_url` tool to any MCP client |

On the roadmap (one new skill per week): `schema-forge` (JSON-LD generator), `ai-visibility-check` (AI-crawler & llms.txt readiness), `persian-keyword-tools` (Hazm-powered keyword normalization/clustering).

## Use it in Claude Code

Copy the skill into your skills folder:

```bash
git clone https://github.com/mohammad-abbasi-sh/agent-seo-skills
cp -r agent-seo-skills/skills/site-audit ~/.claude/skills/
```

Then just ask Claude: **"Audit https://example.com for SEO"** — the skill loads, runs the audit script, and reports the score with prioritized fixes.

## Use it as an MCP server (Claude Desktop / Claude Code / Cursor)

```bash
claude mcp add agent-seo -- python3 /path/to/agent-seo-skills/mcp-server/seo_mcp_server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "agent-seo": {
      "command": "python3",
      "args": ["/path/to/agent-seo-skills/mcp-server/seo_mcp_server.py"]
    }
  }
}
```

Then ask: **"Use audit_url on https://example.com"**.

## Run it yourself (no agent)

```bash
python3 skills/site-audit/scripts/seo_audit.py https://example.com --json
python3 skills/striking-distance/scripts/gsc_analyze.py <gsc-export.csv>
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Hermetic end-to-end test: serves a fixture page locally, performs the MCP handshake, calls `audit_url`, and validates the report.

## Principles

- **Deterministic tools, honest output.** The scripts measure; the agent interprets. No fabricated traffic, volume, or backlink numbers.
- **Local-first.** No API keys, no accounts, no telemetry.
- **Built in public, one skill per week** by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — SEO Manager & Product Manager, working at the SEO × AI edge.

## License

MIT
