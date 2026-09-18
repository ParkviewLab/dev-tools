#!/usr/bin/env python3
"""Re-run git-cliff over every one of the 81 release ranges (a first release's
from its root commit), with each repository's cliff.toml as at the tag and again
with its `^Merge` parser line removed, and report in how many ranges the output
differs.  Writes the edited configurations to cliffcfg_nomerge/ and the result to
cliff_nomerge.json."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "cliffcfg_nomerge"
OUT.mkdir(exist_ok=True)


def sh(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(a, capture_output=True, text=True, errors="replace")


def main() -> None:
    d = json.load(open(HERE / "raw_measure.json"))
    total, differ = 0, []
    for name, v in d["repos"].items():
        repo = HERE / "clones" / name
        for row in v["rows"]:
            t, prev = row["tag"], row["prev"]
            cfg = HERE / "cliffcfg" / f"{name}.{t}.toml"
            edited = OUT / f"{name}.{t}.toml"
            edited.write_text("\n".join(l for l in cfg.read_text().splitlines() if "^Merge" not in l) + "\n")
            if prev:
                rng = f"{prev}..{t}"
            else:
                root = sh("git", "-C", str(repo), "rev-list", "--max-parents=0", t).stdout.split()[0]
                rng = f"{root}..{t}"
            a = sh("git-cliff", "--repository", str(repo), "--config", str(cfg), rng).stdout
            b = sh("git-cliff", "--repository", str(repo), "--config", str(edited), rng).stdout
            total += 1
            if a != b:
                differ.append(f"{name} {t}")
    result = {"git_cliff": sh("git-cliff", "--version").stdout.strip(), "ranges": total, "differing": differ}
    json.dump(result, open(HERE / "cliff_nomerge.json", "w"), indent=1)
    print(result)


if __name__ == "__main__":
    main()
