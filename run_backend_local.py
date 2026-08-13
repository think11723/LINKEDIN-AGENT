"""Phase 7.10 launcher: load .env then .env.local (overrides), then start uvicorn."""
import os
from pathlib import Path

for name in (".env", ".env.local"):
    p = Path(__file__).parent / name
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )