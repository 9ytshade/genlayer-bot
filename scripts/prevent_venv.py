#!/usr/bin/env python3
import sys
import subprocess
import re

try:
    out = subprocess.check_output(["git", "diff", "--cached", "--name-only"]).decode()
except subprocess.CalledProcessError:
    # If git fails for any reason, be permissive (do not block commit)
    sys.exit(0)

files = out.splitlines()
pattern = re.compile(r'(^|/)(?:\.venv|venv)(/|$)')
bad = [f for f in files if pattern.search(f)]
if bad:
    print("Refusing to commit virtualenv files:")
    for f in bad:
        print("  -", f)
    print("\nRemove these files from the commit (git reset <file>) or add them to .gitignore before committing.")
    sys.exit(1)

sys.exit(0)
