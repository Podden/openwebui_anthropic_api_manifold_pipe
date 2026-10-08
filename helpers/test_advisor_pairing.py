"""Self-check for the advisor tool's executor-pair guard under dated model ids.

Opus 5.5 has no row in Anthropic's advisor compatibility table, so the pipe must
skip the advisor tool for an Opus-5.5 executor. Azure/custom proxies hand us dated
ids like ``claude-opus-5-5-20260215``; a literal ``== "claude-opus-5-5"`` check
misses those, re-enabling the advisor and 400-ing the request. The executor->advisor
fallback lookup has the same dated-id blind spot. Both paths must normalize the id
exactly like ``get_model_info`` does.

Runs without OpenWebUI and without network access: the method group is loaded from
``src/`` and exercised against fake valves and a stub ``get_model_info``.

Usage:
    python helpers/test_advisor_pairing.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src" / "anthropic_pipe"
TOOLS_PATH = SRC / "request" / "tools.py"
MODELS_PATH = SRC / "shared" / "models.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_tools = _load("_adv_tools", TOOLS_PATH)
_models = _load("_adv_models", MODELS_PATH)

# The compiled artifact resolves these from module scope inside class Pipe;
# in isolation the tool-search deferral helper and json are all this path needs.
_tools.json = json
_tools.normalize_tool_name_list = lambda value: set()


class FakeValves:
    ENABLE_BASH_TOOL = False
    ENABLE_TEXT_EDITOR_TOOL = False
    WEB_SEARCH = False
    WEB_FETCH = False
    ENABLE_PROGRAMMATIC_TOOL_CALLING = False


class FakeUserValves:
    def __init__(self, advisor_model: str):
        self.ENABLE_ADVISOR_TOOL = True
        self.ADVISOR_MODEL = advisor_model
        self.ADVISOR_MAX_USES = 0
        self.ADVISOR_CACHING = "off"
        self.ENABLE_DYNAMIC_FILTERING = False
        self.ENABLE_TOOL_SEARCH = False
        self.TOOL_SEARCH_EXCLUDE_TOOLS = ""
        self.TOOL_SEARCH_MAX_DESCRIPTION_LENGTH = 1000
        self.TOOL_SEARCH_TYPE = "bm25"


class Pipe(_tools.PipeRequestToolsMethods, _models.PipeModelSupportMethods):
    valves = FakeValves()

    def get_model_info(self, model_name):  # noqa: D401 - stub
        return {}


def _advisor_tool(model_name: str, advisor_model: str = "claude-opus-5"):
    pipe = Pipe()
    tools, _ = pipe._convert_tools_to_claude_format(
        __tools__={},
        body={},
        actual_model_name=model_name,
        __user__={"valves": FakeUserValves(advisor_model)},
        __metadata__={},
    )
    return next((t for t in tools if t.get("name") == "advisor"), None)


def check(desc: str, cond: bool):
    print(f"{'PASS' if cond else 'FAIL'}: {desc}")
    if not cond:
        check.failed = True


check.failed = False

# 1. Normalizer strips a trailing -YYYYMMDD suffix, leaves other ids untouched.
check(
    "_normalize_model_name strips dated suffix",
    Pipe._normalize_model_name("claude-opus-5-5-20260215") == "claude-opus-5-5",
)
check(
    "_normalize_model_name leaves undated id untouched",
    Pipe._normalize_model_name("claude-opus-5-5") == "claude-opus-5-5",
)

# 2. The regression target: a dated Opus-5.5 id must skip the advisor entirely.
check(
    "dated claude-opus-5-5-20260215 -> advisor skipped",
    _advisor_tool("claude-opus-5-5-20260215") is None,
)
# 3. The undated case must keep skipping (no regression).
check(
    "undated claude-opus-5-5 -> advisor skipped",
    _advisor_tool("claude-opus-5-5") is None,
)

# 4. A dated non-Opus-5.5 executor still gets an advisor, and the executor->advisor
#    fallback lookup resolves on the normalized id. Fable 5 pairs only with Fable 5,
#    so an opus-5 advisor must be downgraded to claude-fable-5 — which only happens
#    when the dated id is normalized before the valid_advisors lookup.
fable = _advisor_tool("claude-fable-5-20260101", advisor_model="claude-opus-5")
check(
    "dated claude-fable-5-* -> advisor appended",
    fable is not None,
)
check(
    "dated claude-fable-5-* -> advisor downgraded to claude-fable-5 (normalized lookup)",
    fable is not None and fable.get("model") == "claude-fable-5",
)

if check.failed:
    print("\nFAILURES above")
    sys.exit(1)
print("\nAll advisor-pairing checks passed")
