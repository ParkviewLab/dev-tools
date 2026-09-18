#!/usr/bin/env python3
"""Parts two and three: run proposed_list2 over every release of the ten
repositories, compare with the truth, and recount the published side."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import proposed_list2 as P  # noqa: E402

CLONES = HERE / "clones"
DATA = HERE / "data"
REPOS = ["pensa-grex", "deco-assaying", "smalt-mcp", "ebony-enriching", "conception-space",
         "flint-slating", "jonobones", "paper-boxing", "cobalt-grinding", "cogrind-workshop"]
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
MAINT = {"build", "chore", "ci", "style"}


def git(repo: Path, *a: str, check: bool = True) -> str:
    p = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, errors="replace")
    if check and p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout


def changelog_section(text: str | None, tag: str) -> str | None:
    if text is None:
        return None
    out, on, found = [], False, False
    for ln in text.splitlines():
        if ln.startswith("## "):
            on = bool(re.match(rf"^## \[?{re.escape(tag)}\]?(\s|$)", ln))
            found = found or on
            continue
        if on:
            out.append(ln)
    return "\n".join(out) if found else None


def parse_body(body: str) -> dict:
    """List lines are '- ' or '* ' lines under a heading other than Highlights."""
    heading, items, highlights = None, [], []
    for ln in body.splitlines():
        if ln.startswith("#"):
            heading = ln.strip("# ").strip()
            continue
        if heading == "Highlights":
            if ln.strip():
                highlights.append(ln.strip())
            continue
        if ln.startswith(("- ", "* ")):
            nums = [int(x) for x in re.findall(r"\(#(\d+)\)", ln)]
            h = re.search(r"\(([0-9a-f]{7,40})\)\s*$", ln)
            items.append({"heading": heading, "line": ln, "prs": nums, "hash": h.group(1) if h else None})
    return {"items": items, "highlights": " ".join(highlights)}


def main() -> None:
    evidence: dict = {"repos": {}, "totals": {}}
    for name in REPOS:
        repo = CLONES / name
        prs_list = json.load(open(DATA / f"{name}.prs.json"))
        prs = {p["number"]: p for p in prs_list}
        oid = {n: (p.get("mergeCommit") or {}).get("oid") for n, p in prs.items()}
        releases = {r["tagName"] for r in json.load(open(DATA / f"{name}.releases.json"))}
        cl_main = (DATA / f"{name}.CHANGELOG.main.md")
        cl_text = cl_main.read_text() if cl_main.exists() and cl_main.stat().st_size else None
        tags = sorted([t for t in git(repo, "tag").split() if TAG.match(t)],
                      key=lambda t: tuple(map(int, TAG.match(t).groups())))
        H = P.History(P.Git(str(repo)), prs)

        # Commit -> pull request, for mapping published hashes: GitHub-made commits,
        # cherry-picks, and the own commits of real merges of non-carrier pull requests.
        belongs: dict[str, int] = {}
        for sha, (kind, n) in H.github_attr.items():
            belongs[sha] = n
            if kind.startswith("merge") and not H.is_carrier(n):
                ps = H.commits[sha]["parents"]
                for c in git(repo, "rev-list", *ps[1:], f"^{ps[0]}").split():
                    if c not in H.github_attr:
                        belongs.setdefault(c, n)
        for sha in H.commits:
            if sha not in belongs:
                a = H.attribute(sha)
                if a:
                    belongs[sha] = a[1]

        rows, prev = [], None
        for t in tags:
            res = P.build(str(repo), prev, t, prs_list)
            rng = set(git(repo, "rev-list", f"{prev}..{t}" if prev else t).split())
            truth = sorted(n for n, o in oid.items() if o in rng)
            carriers = sorted(n for n in truth if H.is_carrier(n))
            expected = sorted(set(truth) - set(carriers))
            listed = res["listed"]
            missing = sorted(set(expected) - set(listed))
            extra = sorted(set(listed) - set(expected))
            explain = []
            for n in missing:
                sh = next((a for a in res["already_shipped"] if a["number"] == n), None)
                if sh:
                    explain.append({"pr": n, "kind": "missing", "explained": True,
                                    "why": f"R4: already shipped in an earlier release by {sh['evidence']}; "
                                           f"GitHub's merge commit {oid[n][:10]} lies in this range"})
                else:
                    explain.append({"pr": n, "kind": "missing", "explained": False, "why": "UNEXPLAINED"})
            for n in extra:
                e = next(x for g in res["groups"].values() for x in g if x["number"] == n)
                if any(v.startswith("cherry-pick") for v in e["via"]):
                    later = next((t2 for t2 in tags if oid.get(n) and oid[n] in set(git(repo, "rev-list", t2).split())), None)
                    explain.append({"pr": n, "kind": "extra", "explained": True,
                                    "why": f"R2(c): listed as a cherry-pick ({', '.join(e['commits'])} of "
                                           f"{', '.join(e.get('originals', []))}); GitHub's merge commit "
                                           f"{(oid.get(n) or '')[:10]} first reaches a release in {later}"})
                else:
                    explain.append({"pr": n, "kind": "extra", "explained": False,
                                    "why": f"UNEXPLAINED via {e['via']} commits {e['commits']}"})

            # ---- published side
            src, body = "none", None
            if t in releases:
                rel = json.load(open(DATA / "rel" / f"{name}.{t}.json"))
                body, src = rel.get("body") or "", "release"
            else:
                sec = changelog_section(cl_text, t)
                if sec is not None:
                    body, src = sec, "changelog-main"
            parsed = parse_body(body or "")
            pub_nums = sorted({n for it in parsed["items"] for n in it["prs"]})
            omitted = sorted(set(expected) - set(pub_nums))
            pub_not_expected = sorted(set(pub_nums) - set(expected))
            # hash-published: an item's hash belongs to an omitted PR
            hash_pub: dict[int, list[str]] = {}
            noise = []
            for it in parsed["items"]:
                if it["prs"]:
                    continue
                full = git(repo, "rev-parse", "--verify", "--quiet", f"{it['hash']}^{{commit}}", check=False).strip() if it["hash"] else ""
                n = belongs.get(full)
                if n is not None:
                    hash_pub.setdefault(n, []).append(it["hash"])
                    continue
                c = H.commits.get(full)
                subj = c["subject"] if c else "?"
                rsn, _ = P.bookkeeping_nonmerge(P.Git(str(repo)), full, c["parents"]) if c and len(c["parents"]) < 2 else (None, "")
                if c and rsn == "changelog-only" and (c["cn"].startswith("github-actions") or subj.startswith("docs(changelog)")):
                    kind = "release-job changelog commit"
                elif c:
                    kind = "real change without a pull request"
                else:
                    kind = "hash not found"
                noise.append({"line": it["line"], "hash": it["hash"], "commit_subject": subj, "kind": kind})
            first = prev is None
            has_list = bool(parsed["items"])
            omissions = []
            for n in omitted:
                pr = prs[n]
                ttl = pr["title"]
                # R6 title as the rule computes it, for the prefix test
                gh = next((s for s, (k, m) in H.github_attr.items() if m == n and s == oid[n]), None)
                kind = H.github_attr[gh][0] if gh else None
                if kind in ("squash", "merge-titled"):
                    ttl = P.strip_suffix(H.commits[gh]["subject"])
                typ = P.conventional(ttl)["type"]
                if first and not has_list:
                    cause = "first release's empty range"
                elif not has_list:
                    cause = "tag published with no list"
                elif typ in MAINT or typ is None or typ not in P.GROUP_OF_TYPE:
                    cause = "written prefix policy"
                elif kind == "merge-default-title":
                    cause = "real merge at default title skipped by ^Merge"
                else:
                    cause = "other"
                omissions.append({"pr": n, "title": ttl, "type": typ, "merge_kind": kind, "cause": cause,
                                  "published_by_hash": hash_pub.get(n, [])})
            rows.append({
                "tag": t, "prev": prev, "commits_in_range": res["commits_in_range"],
                "truth": truth, "carriers": carriers, "expected": expected, "listed": listed,
                "proposed_missing": missing, "proposed_extra": extra, "explanations": explain,
                "direct_commits": res["direct_commits"], "bookkeeping": res["bookkeeping"],
                "already_shipped": res["already_shipped"], "warnings": res["warnings"],
                "groups": {g: [x["number"] for x in v] for g, v in res["groups"].items()},
                "published_source": src, "published_items": len(parsed["items"]),
                "published_prs": pub_nums, "published_not_expected": pub_not_expected,
                "omitted": omissions, "noise": noise, "highlights": parsed["highlights"],
                "section": res["section"],
            })
            prev = t
        evidence["repos"][name] = {"tags": tags, "releases_with_github_release": sorted(releases & set(tags)),
                                   "rows": rows}
        print(name, "done", file=sys.stderr)
    json.dump(evidence, open(HERE / "raw_measure.json", "w"), indent=1)


if __name__ == "__main__":
    main()
