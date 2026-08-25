"""Check the local OpenAI Codex SDK boundary without running a target Agent."""
from __future__ import annotations

import json


def main() -> int:
    try:
        from openai_codex import Codex

        with Codex() as codex:
            metadata = getattr(codex, "metadata", None)
            print(json.dumps({
                "status": "ready",
                "sdk": "openai-codex",
                "runtime_version": getattr(metadata, "version", None),
            }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "blocked",
            "sdk": "openai-codex",
            "error_type": type(exc).__name__,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
