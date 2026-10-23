#!/usr/bin/env python3
"""agent-seo-skills MCP server — zero-dependency (Python standard library only).

Exposes the site-audit engine as an MCP tool over stdio, so Claude Code,
Claude Desktop, Cursor, Codex and any other MCP client can audit pages
directly. Implements the MCP JSON-RPC handshake (initialize, tools/list,
tools/call, ping) without the MCP SDK.

Usage:
    python3 seo_mcp_server.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "site-audit" / "scripts"))
from seo_audit import audit  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "agent-seo-skills", "version": "0.1.0"}

TOOLS = [
    {
        "name": "audit_url",
        "description": (
            "Audit a web page's on-page SEO: HTTP status, title, meta "
            "description, H1, canonical, robots meta, Open Graph, JSON-LD "
            "schema, images and alt coverage, links and word count. "
            "Returns a structured report with a 0-100 SEO score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The page URL to audit, e.g. https://example.com/page",
                }
            },
            "required": ["url"],
        },
    }
]


def summarize(report: dict) -> str:
    lines = [
        f"SEO audit for {report['url']}",
        f"Score: {report['score']}/100 · HTTP {report['status']} · "
        f"{report['response_time_s']}s · {report['word_count']} words",
        f"Title ({len(report['title'])} chars): {report['title'] or 'MISSING'}",
        f"Meta description ({len(report['meta_description'])} chars): "
        f"{report['meta_description'] or 'MISSING'}",
        f"H1 count: {len(report['h1'])}",
        f"Canonical: {report['canonical'] or 'MISSING'}",
        f"JSON-LD blocks: {report['json_ld_blocks']} {report['json_ld_types']}",
        f"Images: {report['images']} ({report['images_with_alt']} with alt)",
    ]
    return "\n".join(lines)


def handle(request: dict) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        if name != "audit_url":
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        url = (params.get("arguments") or {}).get("url", "")
        try:
            report = audit(url)
            text = summarize(report) + "\n\n" + json.dumps(report, ensure_ascii=False, indent=2)
            result = {"content": [{"type": "text", "text": text}], "isError": False}
        except Exception as exc:  # fetch/parse failure: report, don't crash
            result = {"content": [{"type": "text", "text": f"Audit failed for {url}: {exc}"}],
                      "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
