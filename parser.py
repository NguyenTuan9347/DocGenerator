import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from pathlib import Path


class TokenType(Enum):
    FUNC_SIGNATURE = 2
    CLASS_NAME = 3


@dataclass
class Token:
    content: str
    type: TokenType


@dataclass
class DocumentNode:
    identifier: Token
    description: Optional[str] = None
    children: List["DocumentNode"] = field(default_factory=list)
    indent_level: int = 0


GET_FUNC = r"^(\s*)def\s+(\w+)\s*\(.*?\)\s*"
GET_CLASS = r"^(\s*)class\s+(\w+)(?:\s*\([^)]*\))?\s*"


def extract_docstring(lines: List[str], start_idx: int) -> tuple[Optional[str], int]:
    """
    Extract docstring starting from the given index.
    Returns (docstring, next_line_index)
    """
    if start_idx >= len(lines):
        return None, start_idx

    line = lines[start_idx].strip()

    docstring_patterns = [
        r'^"""(.*?)"""$',  # Single line triple quotes
        r"^'''(.*?)'''$",  # Single line single quotes
        r'^"""(.*)$',  # Multi-line triple quotes start
        r"^'''(.*)$",  # Multi-line single quotes start
    ]

    # Single line docstring
    for pattern in docstring_patterns[:2]:
        match = re.match(pattern, line, re.DOTALL)
        if match:
            return f'"""{match.group(1)}"""', start_idx + 1

    for i, pattern in enumerate(docstring_patterns[2:]):
        match = re.match(pattern, line)
        if match:
            quote_type = '"""' if i == 0 else "'''"
            docstring_lines = [line]
            idx = start_idx + 1

            while idx < len(lines):
                current_line = lines[idx]
                docstring_lines.append(current_line.strip())
                if current_line.strip().endswith(quote_type):
                    break
                idx += 1

            return "\n".join(docstring_lines), idx + 1

    return None, start_idx


def parse(lines: List[str], parent_indent: int = -1) -> List[DocumentNode]:
    """
    Recursively parse Python code into DocumentNode tree.
    Detects indentation automatically.
    """
    nodes = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        func_match = re.match(GET_FUNC, line)
        class_match = re.match(GET_CLASS, line)

        if func_match or class_match:
            match = func_match or class_match
            indent = len(match.group(1))

            # Skip if this definition is at a deeper level than expected
            if parent_indent >= 0 and indent <= parent_indent:
                break

            token_type = (
                TokenType.FUNC_SIGNATURE if func_match else TokenType.CLASS_NAME
            )
            signature = line.strip()

            docstring = None
            next_idx = i + 1

            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1

            if next_idx < len(lines):
                next_line_indent = len(lines[next_idx]) - len(lines[next_idx].lstrip())
                if next_line_indent > indent and (
                    '"""' in lines[next_idx] or "'''" in lines[next_idx]
                ):
                    docstring, next_idx = extract_docstring(lines, next_idx)

            node = DocumentNode(
                identifier=Token(signature, token_type),
                description=docstring,
                indent_level=indent,
            )

            # Collect body lines for recursive parsing
            body_lines = []
            current_idx = next_idx if docstring else i + 1

            while current_idx < len(lines):
                current_line = lines[current_idx]

                if not current_line.strip():
                    body_lines.append(current_line)
                    current_idx += 1
                    continue

                current_indent = len(current_line) - len(current_line.lstrip())

                if current_indent <= indent:
                    break

                body_lines.append(current_line)
                current_idx += 1

            if any(line.strip() for line in body_lines):
                node.children = parse(body_lines, indent)

            nodes.append(node)
            i = current_idx
            continue

        i += 1

    return nodes


def print_tree(nodes_by_file: dict[Path, list[DocumentNode]]):
    """Pretty print the document tree for multiple files."""
    for file_path, nodes in nodes_by_file.items():
        print(f"\n{'='*60}")
        print(f"File: {file_path}")
        print("=" * 60)
        _print_nodes(nodes)


def _print_nodes(nodes: list[DocumentNode], level: int = 0):
    display_indent = "  " * level
    for node in nodes:
        signature = node.identifier.content
        if signature.endswith("):"):
            signature = signature[:-1] + ":"

        print(f"{display_indent}{signature} (base indent: {node.indent_level} spaces)")

        if node.description:
            cleaned_desc = node.description.strip()
            if cleaned_desc.startswith('"""') or cleaned_desc.startswith("'''"):
                cleaned_desc = cleaned_desc[3:]
            if cleaned_desc.endswith('"""') or cleaned_desc.endswith("'''"):
                cleaned_desc = cleaned_desc[:-3]
            cleaned_desc = cleaned_desc.strip()

            if cleaned_desc:
                desc_lines = cleaned_desc.split("\n")
                for i, line in enumerate(desc_lines):
                    line = line.strip()
                    if line:
                        prefix = "    " if i > 0 else "  -> "
                        print(f"{display_indent}{prefix}{line}")

        if node.children:
            _print_nodes(node.children, level + 1)


def generate_html(nodes_by_file: dict[Path, list[DocumentNode]], level=0):
    html = []
    indent = "  " * level

    for file_path, nodes in nodes_by_file.items():
        html.append(f"{indent}<h2>{file_path}</h2>")
        html.append(_generate_nodes_html(nodes, level))
    return "\n".join(html)


def _generate_nodes_html(nodes, level=0):
    html = []
    indent = "  " * level

    html.append(f"{indent}<ul>")
    for node in nodes:
        sig = node.identifier.content
        html.append(f"{indent}  <li><strong>{sig}</strong>")

        if node.description:
            desc = node.description.strip()
            if desc.startswith('"""') or desc.startswith("'''"):
                desc = desc[3:]
            if desc.endswith('"""') or desc.endswith("'''"):
                desc = desc[:-3]
            desc = desc.strip()
            if desc:
                html.append(f"{indent}    <div class='desc'>{desc}</div>")

        if node.children:
            html.append(_generate_nodes_html(node.children, level + 2))

        html.append(f"{indent}  </li>")
    html.append(f"{indent}</ul>")

    return "\n".join(html)


def save_html(nodes_by_file: dict[Path, list[DocumentNode]], output_file="index.html"):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Code Index</title>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        ul {{ list-style-type: none; }}
        li {{ margin-bottom: 8px; }}
        .desc {{ color: gray; font-size: 0.9em; margin-left: 1em; }}
        h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 20px; }}
    </style>
</head>
<body>
<h1>Code Index</h1>
{generate_html(nodes_by_file)}
</body>
</html>
"""
    Path(output_file).write_text(html_content, encoding="utf-8")
