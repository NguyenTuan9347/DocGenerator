from pathlib import Path
from parser import parse, print_tree


def main(path: Path):
    """Main function to process Python files"""
    files = []

    if path.is_dir():
        files.extend(list(path.rglob("*.py")))
    elif path.is_file() and path.suffix == ".py":
        files.append(path)
    else:
        print(f"Invalid path or not a Python file: {path}")
        return

    for file in files:
        print(f"\n{'='*60}")
        print(f"Processing: {file}")
        print("=" * 60)

        try:
            with open(file, mode="r", encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()

            nodes = parse(lines)

            if nodes:
                print_tree(nodes)
            else:
                print("No classes or functions found.")

        except Exception as e:
            print(f"Error processing {file}: {e}")


if __name__ == "__main__":
    path = Path(".")
    main(path)
