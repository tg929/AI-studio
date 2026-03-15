#!/usr/bin/env python3

from __future__ import annotations

import uvicorn

from app.ui import create_ui_app


if __name__ == "__main__":
    uvicorn.run(create_ui_app(), host="127.0.0.1", port=8188)
