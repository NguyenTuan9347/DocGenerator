from pathlib import Path
from parser import parse, print_tree, save_html
from collections import defaultdict


def code_to_docs(path: Path):
    """Main function to process Python files"""
    files = []

    if path.is_dir():
        files.extend(list(path.rglob("*.py")))
    elif path.is_file() and path.suffix == ".py":
        files.append(path)
    else:
        print(f"Invalid path or not a Python file: {path}")
        return
    print(files)
    nodes = defaultdict(list)
    for file in files:
        print(f"\n{'='*60}")
        print(f"Processing: {file}")
        print("=" * 60)

        try:
            with open(file, mode="r", encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()

            nodes[file.resolve()] = parse(lines)

        except Exception as e:
            print(f"Error processing {file}: {e}")
    save_html(nodes, f"index.html")
    print_tree(nodes)


if __name__ == "__main__":
    path = Path(".")
    code_to_docs(path)
