import re

with open("src/codebase_dump.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

current_file = ""
output = []
for line in lines:
    if line.startswith("File: "):
        current_file = line.strip()
        output.append("\n" + current_file)
    elif line.startswith("def ") or line.startswith("class ") or line.startswith("    def "):
        output.append(line.rstrip())

with open("repo_summary.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

