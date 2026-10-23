"""End-to-end test: MCP handshake + tools/call against a local fixture page.

Hermetic — serves a fixed HTML page on 127.0.0.1, no internet needed.
Run: python3 -m unittest discover -s tests -v
"""

import json
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp-server" / "seo_mcp_server.py"

FIXTURE = """<!doctype html><html><head>
<title>Fixture Page Title For Testing Purposes</title>
<meta name="description" content="A fixture description that is long enough to be
realistic for an SEO audit unit test of the MCP server end to end flow.">
<link rel="canonical" href="http://127.0.0.1/fixture">
<script type="application/ld+json">{"@type": "WebPage"}</script>
</head><body><h1>Hello fixture</h1>
<img src="a.png" alt="A"><img src="b.png">
<p>Some body text for word counting purposes here.</p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = FIXTURE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def rpc(proc, payload):
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


class TestMcpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def test_handshake_and_audit(self):
        proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        )
        try:
            init = rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2024-11-05",
                                         "capabilities": {},
                                         "clientInfo": {"name": "test", "version": "0"}}})
            self.assertEqual(init["result"]["serverInfo"]["name"], "agent-seo-skills")

            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()

            tools = rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = [t["name"] for t in tools["result"]["tools"]]
            self.assertIn("audit_url", names)

            call = rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                              "params": {"name": "audit_url",
                                         "arguments": {"url": f"http://127.0.0.1:{self.port}/fixture"}}})
            self.assertFalse(call["result"]["isError"])
            text = call["result"]["content"][0]["text"]
            self.assertIn("Score:", text)
            report = json.loads(text.split("\n\n", 1)[1])
            self.assertEqual(report["status"], 200)
            self.assertEqual(len(report["h1"]), 1)
            self.assertEqual(report["json_ld_blocks"], 1)
            self.assertGreater(report["score"], 50)
        finally:
            proc.terminate()


if __name__ == "__main__":
    unittest.main()
