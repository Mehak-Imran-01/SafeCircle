import json
import os
import sys
import threading
import time
import urllib.request

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn
from app.main import app


class Server(uvicorn.Server):
    def install_signal_handlers(self):
        pass


def run_server(server):
    server.run()


def test_endpoint(url, desc):
    print(f"\n--- Testing {desc}: {url} ---")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            print(f"Status Code: {status}")
            try:
                parsed = json.loads(body)
                print(f"Response JSON: {json.dumps(parsed, indent=2)}")
            except Exception:
                print(f"Response: HTML / content received ({len(body)} bytes)")
            return status == 200
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def main():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = Server(config=config)
    t = threading.Thread(target=run_server, args=(server,), daemon=True)
    t.start()

    time.sleep(1.5)

    base = "http://127.0.0.1:8000"
    results = [
        test_endpoint(f"{base}/", "Root Endpoint (GET /)"),
        test_endpoint(f"{base}/health", "Health Endpoint (GET /health)"),
        test_endpoint(f"{base}/api/v1/health", "API v1 Health Endpoint (GET /api/v1/health)"),
        test_endpoint(f"{base}/api/docs", "Swagger Docs (GET /api/docs)"),
        test_endpoint(f"{base}/api/openapi.json", "OpenAPI Schema (GET /api/openapi.json)"),
    ]

    server.should_exit = True
    t.join(timeout=2)

    if all(results):
        print("\n>>> ALL ENDPOINTS VERIFIED SUCCESSFULLY (200 OK)! <<<")
        sys.exit(0)
    else:
        print("\n>>> SOME ENDPOINTS FAILED VERIFICATION! <<<")
        sys.exit(1)


if __name__ == "__main__":
    main()
