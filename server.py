#!/usr/bin/env python3
"""
HTTP server：提供 webhook endpoint，讓 n8n 可以觸發 check_broker.py
端點：
  GET  /           健康檢查
  POST /run?key=X  執行 check_broker（需通過 PASSWORD 驗證）
"""

import os
import sys
import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import check_broker

PORT = int(os.environ.get("PORT", "8080"))
PASSWORD = os.environ.get("PASSWORD", "")


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # 統一輸出到 stdout，讓 Zeabur 日誌抓得到
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _authorized(self, parsed):
        if not PASSWORD:
            return True
        qs = parse_qs(parsed.query)
        key = (qs.get("key") or [""])[0]
        if key == PASSWORD:
            return True
        header_key = self.headers.get("X-Auth-Key", "")
        return header_key == PASSWORD

    def _run(self, parsed):
        if not self._authorized(parsed):
            self._json(401, {"error": "unauthorized"})
            return
        try:
            print("[trigger] 開始執行 check_broker.main()")
            check_broker.main()
            print("[trigger] 完成")
            self._json(200, {"status": "ok"})
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"status": "error", "message": str(e)})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/health"):
            self._json(200, {"status": "ok", "service": "broker-checker"})
            return
        if parsed.path == "/run":
            self._run(parsed)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/run":
            self._run(parsed)
            return
        self._json(404, {"error": "not found"})


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"HTTP server listening on 0.0.0.0:{PORT}")
    print(f"Endpoints: GET /  |  GET|POST /run?key=...")
    server.serve_forever()


if __name__ == "__main__":
    main()
