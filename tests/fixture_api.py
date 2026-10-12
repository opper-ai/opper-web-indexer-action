"""A local HTTP fixture for the actual SDK; no SDK methods are mocked."""

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4


class FixtureAPI:
    def __init__(self, existing=False, reject_document=False):
        self.index = {
            "uuid": str(uuid4()), "name": "fixture-index",
            "created_at": "2026-01-01T00:00:00Z",
        }
        self.exists = existing
        self.reject_document = reject_document
        self.requests = []
        self.documents = []
        self.calls = []
        self.pages = {}
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def respond(self, code, payload, content_type="application/json", headers=None):
                body = json.dumps(payload).encode() if content_type == "application/json" else payload.encode()
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def handle_request(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else None
                fixture.requests.append((self.command, self.path, body))
                if self.command == "GET" and self.path == "/v1/indexes":
                    self.respond(200, [fixture.index] if fixture.exists else [])
                elif self.command == "POST" and self.path == "/v1/indexes":
                    fixture.exists = True
                    self.respond(200, fixture.index)
                elif self.command == "POST" and self.path == "/v1/call":
                    fixture.calls.append(body)
                    metadata = (
                        {"name": "Generated title", "keywords": "fixture, documentation",
                         "last_modified": "2026-01-01", "size": "42", "source": "fixture-source"}
                        if body["name"] == "create_metadata" else
                        {"page_description": "Fixture page description", "keywords": ["fixture", "documentation"]}
                    )
                    self.respond(200, {"json_payload": metadata, "span_id": str(uuid4())})
                elif self.command == "POST" and self.path == f"/v1/indexes/{fixture.index['uuid']}/index":
                    if fixture.reject_document:
                        self.respond(400, {"errors": [{"type": "APIError", "message": "fixture document rejection", "detail": None}]})
                    else:
                        fixture.documents.append(body)
                        self.respond(200, {**body, "uuid": str(uuid4())})
                elif self.command == "POST" and self.path == "/v1/spans":
                    self.respond(200, body)
                elif self.command == "PUT" and self.path.startswith("/v1/spans/"):
                    self.respond(200, body)
                elif self.command == "GET" and self.path in fixture.pages:
                    code, html, headers = fixture.pages[self.path]
                    self.respond(code, html, "text/html", headers)
                else:
                    self.respond(404, {"error": "unknown fixture route"})

            do_GET = handle_request
            do_POST = handle_request
            do_PUT = handle_request

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def run(self, *arguments, cwd="/app", extra_env=None):
        env = {key: value for key, value in os.environ.items() if "proxy" not in key.lower()}
        env.pop("OPPER_API_KEY", None)
        env.update(OPPER_API_URL=self.url, NO_PROXY="*")
        env.update(extra_env or {})
        return subprocess.run(
            ["/app/entrypoint.sh", *arguments], cwd=cwd, env=env,
            text=True, capture_output=True, timeout=30,
        )

    @property
    def created_indexes(self):
        return [body for method, path, body in self.requests if (method, path) == ("POST", "/v1/indexes")]
