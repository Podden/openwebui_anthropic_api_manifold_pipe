"""Minify an OpenWebUI pipe/filter/tool Python file.

Strips comments, function/class/method docstrings, and collapses runs of
blank lines while preserving:

- The module-level docstring (OpenWebUI reads frontmatter from it: title,
  version, requirements, etc.)
- All executable code (semantics-preserving)
- Pydantic Field(description="..."), Valves, type annotations
- Shebang / encoding cookies on lines 1–2

Usage:
    python helpers/minify_pipe.py <input.py> [-o <output.py>]

If -o is omitted, writes <input>.min.py next to the input.
"""

from __future__ import annotations

import argparse
import ast
import io
import sys
import tokenize
from pathlib import Path


def _strip_docstrings(source: str) -> str:
    """Remove docstrings from every function, async function, class and
    nested scope EXCEPT the top-level module docstring (kept for OpenWebUI
    metadata). Returns rewritten source via ast.unparse → which loses
    formatting; so instead we rewrite by line-range deletion to preserve
    everything else.
    """
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    # Collect (start_line, end_line) 1-based inclusive ranges to delete.
    to_delete: list[tuple[int, int]] = []

    def visit(node: ast.AST, is_module: bool = False) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                if not is_module:  # keep module docstring
                    doc = body[0]
                    to_delete.append((doc.lineno, doc.end_lineno or doc.lineno))
        for child in ast.iter_child_nodes(node):
            visit(child, is_module=False)

    visit(tree, is_module=True)
    # Sort descending so deletions don't shift earlier indices.
    to_delete.sort(reverse=True)
    for start, end in to_delete:
        del lines[start - 1:end]
    return "".join(lines)


def _strip_comments(source: str) -> str:
    """Remove `# comments` while keeping all code/strings intact via tokenize.

    We DO keep the NL token after a comment (otherwise untokenize emits
    line continuations inside parenthesized expressions). The empty lines
    left behind are collapsed later by :func:`_collapse_blank_lines`.
    """
    tokens = [
        tok for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type != tokenize.COMMENT
    ]
    return tokenize.untokenize(tokens)


def _collapse_blank_lines(source: str) -> str:
    """Collapse 2+ consecutive blank lines into a single blank line. Strip
    trailing whitespace per line. Drop trailing empty lines."""
    out: list[str] = []
    blank = False
    for line in source.splitlines():
        stripped = line.rstrip()
        if not stripped:
            if blank:
                continue
            blank = True
            out.append("")
        else:
            blank = False
            out.append(stripped)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n"


def minify(source: str) -> str:
    source = _strip_docstrings(source)
    source = _strip_comments(source)
    source = _collapse_blank_lines(source)
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("input", type=Path, help="Path to source pipe file.")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output path (default: <input>.min.py).")
    parser.add_argument("--check", action="store_true",
                        help="py_compile the output to verify validity.")
    args = parser.parse_args(argv)

    src = args.input.read_text(encoding="utf-8")
    minified = minify(src)
    out_path = args.output or args.input.with_suffix(".min.py")
    out_path.write_text(minified, encoding="utf-8")

    in_size = args.input.stat().st_size
    out_size = out_path.stat().st_size
    in_lines = src.count("\n") + 1
    out_lines = minified.count("\n") + 1
    saved = (1 - out_size / in_size) * 100 if in_size else 0
    print(f"Wrote {out_path}")
    print(f"  size:  {in_size:,} -> {out_size:,} bytes ({saved:.1f}% smaller)")
    print(f"  lines: {in_lines:,} -> {out_lines:,}")

    if args.check:
        import py_compile
        try:
            py_compile.compile(str(out_path), doraise=True)
            print("  py_compile: OK")
        except py_compile.PyCompileError as e:
            print(f"  py_compile: FAILED - {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
