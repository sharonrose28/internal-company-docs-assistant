"""Railway-compatible API entry point that honors the injected PORT."""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
        access_log=False,
    )


if __name__ == "__main__":
    main()
