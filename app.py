from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.abstractions import AbstractionLibrary
from server.test_runner import run_startup_suite
from server.workspace import WORKSPACE_VERSION, WorkspaceStore, starting_workspace

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMAGES_DIR =