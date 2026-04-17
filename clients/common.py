#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os


def base_url() -> str:
    host = os.environ.get("KYTOS_HOST", "localhost")
    return f"http://{host}:8181/api"


def headers() -> dict:
    return {"Content-Type": "application/json"}
