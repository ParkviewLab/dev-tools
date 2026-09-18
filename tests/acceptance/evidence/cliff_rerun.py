#!/usr/bin/env python3
"""Re-run git-cliff, with each repository's own cliff.toml (as at the tag, else
as on origin/main), over every release range, to see what the current
per-repository generator's list would contain.  Adds 'cliff_rerun' to each row of
raw_measure.json."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLONES = HERE / "clones"
TMP = HERE / "cliffcfg"
TMP.mkdir(exist_ok=True)


def sh(*a: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(a, capture_output=True, text=True, errors="replace", cwd=cwd)


def main() -> None:
    d = json.load(open(HERE / "raw_measure.json"))
    for name, v in d["repos"].items():
        repo = CLONES / name
        for row in v["rows"]:
            t, prev = row["tag"], row["prev"]
            cfg_src = t
            cfg = sh("git", "-C", str(repo), "show", f"{t}:cliff.toml")
            if cfg.returncode:
                cfg_src = "origin/main"
                cfg = sh("git", "-C", str(repo), "show", "origin/main:cliff.toml")
            path = TMP / f"{name}.{t}.toml"
            path.write_text(cfg.stdout)
            out = {}
            ranges = {"as_published": f"{prev}..{t}" if prev else f"..{t}"}
            if not prev:
                root = sh("git", "-C", str(repo), "rev-list", "--max-parents=0", t).stdout.split()
                ranges["first_release_from_root"] = f"{root[0]}..{t}"
            for label, rng in ranges.items():
                p = sh("git-cliff", "--repository", str(repo), "--config", str(path), rng)
                body = p.stdout
                items = [ln for ln in body.splitlines() if ln.startswith(("- ", "* "))]
                out[label] = {
                    "range": rng, "rc": p.returncode, "items": len(items),
                    "prs": sorted({int(x) for ln in items for x in re.findall(r"\(#(\d+)\)", ln)}),
                    "lines": items,
                }
            row["cliff_rerun"] = {"config_from": cfg_src, **out}
    json.dump(d, open(HERE / "raw_measure.json", "w"), indent=1)


if __name__ == "__main__":
    main()
