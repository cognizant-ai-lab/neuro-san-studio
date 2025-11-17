import re
import argparse
import os


# This function replaces the "model_name" value in the given file with a new model name.
def replace_model_name(filepath, new_model):
    # Read the file contents
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Match "model_name": "xxx", and replace it while preserving formatting
    pattern = r'(?P<key>"model_name"\s*:\s*")(?P<val>[^"]+)(?P<end>"\s*,?)'
    replaced, count = re.subn(pattern, rf"\g<key>{new_model}\g<end>", content)

    if count == 0:
        # Warn if no model_name was found
        print(f"⚠️ model_name not found: {filepath}")
    else:
        # Overwrite the file with the updated content
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(replaced)
        print(f'✅ Updated model_name → "{new_model}" in: {filepath}')


if __name__ == "__main__":
    # Define CLI arguments
    parser = argparse.ArgumentParser(
        description="Replace model_name in .hocon files (non-destructive)"
    )
    parser.add_argument("--file", help="Single .hocon file to update")
    parser.add_argument("--dir", help="Directory to search for .hocon files")
    parser.add_argument(
        "--model", required=True, help="New model name to set (e.g. llama3.1)"
    )
    args = parser.parse_args()

    # If --file is specified, update that one .hocon file
    if args.file:
        replace_model_name(args.file, args.model)

    # If --dir is specified, update all .hocon files in that directory
    elif args.dir:
        for root, _, files in os.walk(args.dir):
            for file in files:
                if file.endswith(".hocon") or file.endswith(".conf"):
                    filepath = os.path.join(root, file)
                    replace_model_name(filepath, args.model)

    # Show error if neither --file nor --dir is specified
    else:
        print("❗ Please specify either --file or --dir.")
