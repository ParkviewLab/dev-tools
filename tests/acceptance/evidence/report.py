#!/usr/bin/env python3
"""Assemble evidence2.json and the tables of measure.md from raw_measure.json,
accounting.json and synthetic/results.json.  measure.md is produced from
measure_template.md by replacing {{NAME}} with the table NAME."""
from __future__ import annotations

import collections
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = json.load(open(HERE / "raw_measure.json"))
ACC = json.load(open(HERE / "accounting.json"))
SYN = json.load(open(HERE / "synthetic" / "results.json"))
REPOS = list(RAW["repos"])
CAUSES = ["first release's empty range", "tag published with no list", "written prefix policy",
          "real merge at default title skipped by ^Merge", "other"]


def prs_of(r):
    return {p["number"]: p for p in json.load(open(HERE / "data" / f"{r}.prs.json"))}


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


T: dict[str, str] = {}
ev: dict = {"generated": "2026-09-17", "repositories": REPOS}

# ------------------------------------------------------------------ part two
p2_repo, p2_rel, direct_all, explained = [], [], {}, []
tot2 = collections.Counter()
for r in REPOS:
    rows = RAW["repos"][r]["rows"]
    c = collections.Counter()
    for x in rows:
        c["tags"] += 1
        c["commits"] += x["commits_in_range"]
        c["truth"] += len(x["truth"])
        c["carriers"] += len(x["carriers"])
        c["expected"] += len(x["expected"])
        c["listed"] += len(x["listed"])
        c["missing"] += len(x["proposed_missing"])
        c["extra"] += len(x["proposed_extra"])
        c["exact"] += int(not x["proposed_missing"] and not x["proposed_extra"])
        c["explained_nonexact"] += int(bool(x["proposed_missing"] or x["proposed_extra"]) and all(e["explained"] for e in x["explanations"]))
        c["direct"] += len(x["direct_commits"])
        c["bookkeeping"] += len(x["bookkeeping"])
        for e in x["explanations"]:
            explained.append({"repo": r, "tag": x["tag"], **e})
        for dc in x["direct_commits"]:
            direct_all.setdefault(r, []).append({"tag": x["tag"], "sha": dc["sha"][:7], "subject": dc["subject"],
                                                 "merge": dc["merge"], "why_not_bookkeeping": dc["note"]})
        p2_rel.append({
            "repo": r, "tag": x["tag"], "prev": x["prev"], "commits_in_range": x["commits_in_range"],
            "truth": x["truth"], "carriers": x["carriers"], "expected": x["expected"], "listed": x["listed"],
            "groups": x["groups"], "proposed_missing": x["proposed_missing"], "proposed_extra": x["proposed_extra"],
            "explanations": x["explanations"], "direct_commits": [d["sha"][:7] + " " + d["subject"] for d in x["direct_commits"]],
            "bookkeeping": [{"sha": b["sha"][:7], "subject": b["subject"], "reason": b["reason"]} for b in x["bookkeeping"]],
            "already_shipped": x["already_shipped"], "warnings": x["warnings"], "section": x["section"],
        })
    acc = ACC[r]
    p2_repo.append([r, c["tags"], c["commits"], c["truth"], c["carriers"], c["expected"], c["listed"],
                    c["missing"], c["extra"], f"{c['exact']} + {c['explained_nonexact']}", c["direct"],
                    acc["absorbed"], c["bookkeeping"]])
    tot2.update(c)
    tot2["absorbed"] += acc["absorbed"]
p2_repo.append(["Total", tot2["tags"], tot2["commits"], tot2["truth"], tot2["carriers"], tot2["expected"],
                tot2["listed"], tot2["missing"], tot2["extra"], f"{tot2['exact']} + {tot2['explained_nonexact']}",
                tot2["direct"], tot2["absorbed"], tot2["bookkeeping"]])
T["P2_REPO"] = md_table(["Repository", "Tags", "Commits in ranges", "Truth", "Carriers", "Expected", "Listed",
                         "Missing", "Extra", "Exact + explained", "Direct commits", "Absorbed into real merges",
                         "Bookkeeping"], p2_repo)

rows = []
for x in p2_rel:
    rows.append([x["repo"], x["tag"], x["commits_in_range"], len(x["truth"]),
                 ", ".join(f"#{n}" for n in x["carriers"]) or "", len(x["expected"]), len(x["listed"]),
                 ", ".join(f"#{n}" for n in x["proposed_missing"]) or "", ", ".join(f"#{n}" for n in x["proposed_extra"]) or "",
                 len(x["direct_commits"]), len(x["bookkeeping"])])
T["P2_REL"] = md_table(["Repository", "Tag", "Commits", "Truth", "Carriers", "Expected", "Listed", "Missing",
                        "Extra", "Direct", "Bookkeeping"], rows)

rows = []
for r in REPOS:
    for d in direct_all.get(r, []):
        rows.append([r, d["tag"], f"`{d['sha']}`", d["subject"].replace("|", "\\|"), d["why_not_bookkeeping"].replace("|", "\\|")])
T["P2_DIRECT"] = md_table(["Repository", "Tag", "Commit", "Subject", "Why it is not bookkeeping"], rows)
T["P2_DIRECT_COUNTS"] = md_table(["Repository", "Direct commits"],
                                 [[r, len(direct_all.get(r, []))] for r in REPOS] + [["Total", sum(len(v) for v in direct_all.values())]])

bk = collections.Counter()
for x in p2_rel:
    for b in x["bookkeeping"]:
        k = b["reason"].split(":")[0]
        k = "carrier merge, tree equals the automatic merge" if k.startswith("carrier") else {
            "version-only": "(i) version value only", "changelog-only": "(ii) CHANGELOG.md only",
            "merge": "(iii) other merge, tree equals the automatic merge"}[k]
        bk[k] += 1
T["P2_BOOK"] = md_table(["Bookkeeping reason", "Commits"], [[k, v] for k, v in sorted(bk.items())] + [["Total", sum(bk.values())]])

T["P2_EXPLAINED"] = "\n".join(f"- {e['repo']} {e['tag']}, #{e['pr']} {e['kind']}: {e['why']}." for e in explained)

ev["part2"] = {
    "definition": {"truth": "pull requests whose mergeCommit.oid (GitHub API) is in git rev-list prev..tag, or git rev-list tag for a first release",
                   "expected": "truth less carrier pull requests (R3)"},
    "per_repository": [dict(zip(["repo", "tags", "commits_in_ranges", "truth", "carriers", "expected", "listed",
                                 "proposed_missing", "proposed_extra", "exact_plus_explained", "direct_commits",
                                 "absorbed", "bookkeeping"], row)) for row in p2_repo],
    "per_release": p2_rel,
    "explained_cases": explained,
    "direct_commits": direct_all,
    "bookkeeping_by_reason": dict(bk),
    "commit_accounting": ACC,
}

# ------------------------------------------------------------------ part three
p3_repo, p3_rel, omissions, noise_all = [], [], [], []
tot3 = collections.Counter()
cause_by_repo = {}
mech = collections.Counter()
for r in REPOS:
    rows_ = RAW["repos"][r]["rows"]
    prs = prs_of(r)
    c = collections.Counter()
    cc = collections.Counter()
    for x in rows_:
        c["tags"] += 1
        c[x["published_source"]] += 1
        nolist = x["published_items"] == 0
        c["nolist"] += int(nolist)
        c["expected"] += len(x["expected"])
        pub_ok = sorted(set(x["published_prs"]) & set(x["expected"]))
        c["published_by_number"] += len(pub_ok)
        c["omitted"] += len(x["omitted"])
        c["pub_not_expected"] += len(x["published_not_expected"])
        rerun = x["cliff_rerun"]
        for o in x["omitted"]:
            cc[o["cause"]] += 1
            c["by_hash"] += int(bool(o["published_by_hash"]))
            # mechanisms, for the secondary analysis
            m = []
            if x["prev"] is None:
                m.append("empty first-release range")
            if o["merge_kind"] == "merge-default-title":
                m.append("^Merge skip")
            elif o["type"] is None or o["type"] not in ("feat", "fix", "perf", "refactor", "docs", "test", "revert"):
                m.append("prefix or unrecognised type")
            fr = rerun.get("first_release_from_root")
            o2 = dict(o, repo=r, tag=x["tag"], mechanisms=m,
                      listed_by_cliff_with_full_range=(o["pr"] in fr["prs"]) if fr else None)
            omissions.append(o2)
            mech[" + ".join(m) if m else "none"] += 1
        for n in x["noise"]:
            noise_all.append(dict(n, repo=r, tag=x["tag"]))
            c["noise:" + n["kind"]] += 1
        p3_rel.append({
            "repo": r, "tag": x["tag"], "published_source": x["published_source"], "list_items": x["published_items"],
            "expected": x["expected"], "published_prs": x["published_prs"], "published_not_expected": x["published_not_expected"],
            "omitted": x["omitted"], "noise": x["noise"], "highlights": x["highlights"],
            "cliff_rerun": {"config_from": rerun["config_from"],
                            "as_published": {k: rerun["as_published"][k] for k in ("range", "items", "prs")},
                            **({"first_release_from_root": {k: rerun["first_release_from_root"][k] for k in ("range", "items", "prs")}}
                               if "first_release_from_root" in rerun else {})},
        })
    cause_by_repo[r] = cc
    p3_repo.append([r, c["tags"], c["release"], c["changelog-main"], c["none"], c["nolist"], c["expected"],
                    c["published_by_number"], c["omitted"], c["by_hash"],
                    c["noise:release-job changelog commit"], c["noise:real change without a pull request"]])
    tot3.update(c)
p3_repo.append(["Total", tot3["tags"], tot3["release"], tot3["changelog-main"], tot3["none"], tot3["nolist"],
                tot3["expected"], tot3["published_by_number"], tot3["omitted"], tot3["by_hash"],
                tot3["noise:release-job changelog commit"], tot3["noise:real change without a pull request"]])
T["P3_REPO"] = md_table(["Repository", "Tags", "GitHub Release", "CHANGELOG.md section only", "Neither",
                         "Tags with no list", "Expected", "Published by number", "Omitted", "of which by hash",
                         "Noise: release-job commit", "Noise: change without a pull request"], p3_repo)
crow = []
for r in REPOS:
    cc = cause_by_repo[r]
    crow.append([r] + [cc.get(k, 0) for k in CAUSES] + [sum(cc.values())])
tc = collections.Counter()
for cc in cause_by_repo.values():
    tc.update(cc)
crow.append(["Total"] + [tc.get(k, 0) for k in CAUSES] + [sum(tc.values())])
T["P3_CAUSES"] = md_table(["Repository", "First release's empty range", "Tag published with no list",
                           "Written prefix policy", "Default-title merge skipped by ^Merge", "Other", "Total"], crow)
T["P3_MECH"] = md_table(["Mechanisms that dropped the pull request", "Omissions"],
                        [[k, v] for k, v in sorted(mech.items(), key=lambda kv: -kv[1])] + [["Total", sum(mech.values())]])

# cause x merge-kind cross-tab
xt = collections.Counter((o["cause"], o["merge_kind"]) for o in omissions)
T["P3_XTAB"] = md_table(["Cause (prescribed order)", "squash", "real merge, default title", "real merge, titled"],
                        [[k, xt.get((k, "squash"), 0), xt.get((k, "merge-default-title"), 0), xt.get((k, "merge-titled"), 0)]
                         for k in CAUSES])
# first-release: would the generator have listed it with the full range?
fr_rows = []
for r in REPOS:
    os_ = [o for o in omissions if o["repo"] == r and o["cause"] == CAUSES[0]]
    if not os_:
        continue
    yes = [o["pr"] for o in os_ if o["listed_by_cliff_with_full_range"]]
    no = [o["pr"] for o in os_ if not o["listed_by_cliff_with_full_range"]]
    fr_rows.append([r, len(os_), len(yes), ", ".join(f"#{n}" for n in no)])
fr_rows.append(["Total", sum(x[1] for x in fr_rows), sum(x[2] for x in fr_rows), ""])
T["P3_FIRST"] = md_table(["Repository", "First-release omissions", "Listed by git-cliff over root..tag",
                          "Still dropped by the filters"], fr_rows)

om_rows = []
for o in omissions:
    om_rows.append([o["repo"], o["tag"], f"#{o['pr']}", o["title"].replace("|", "\\|")[:80], o["merge_kind"], o["cause"],
                    ", ".join(o["published_by_hash"])])
T["P3_OMISSIONS"] = md_table(["Repository", "Tag", "PR", "Title (R6)", "Merge", "Cause", "Published by hash"], om_rows)
short = {CAUSES[0]: "first", CAUSES[1]: "no list", CAUSES[2]: "prefix", CAUSES[3]: "^Merge", CAUSES[4]: "other"}
rel_rows = []
for x in p3_rel:
    cc_ = collections.Counter(short[o["cause"]] for o in x["omitted"])
    rel_rows.append([x["repo"], x["tag"], {"release": "Release", "changelog-main": "CHANGELOG.md", "none": "none"}[x["published_source"]],
                     x["list_items"], len(x["expected"]), len(set(x["published_prs"]) & set(x["expected"])),
                     ", ".join(f"#{n}" for n in x["published_not_expected"]), len(x["omitted"]),
                     ", ".join(f"{k} {v}" for k, v in sorted(cc_.items())), len(x["noise"])])
T["P3_REL"] = md_table(["Repository", "Tag", "Published", "List lines", "Expected", "Published by number",
                        "Published, not expected", "Omitted", "Causes", "Noise lines"], rel_rows)
T["P3_NOISE"] = md_table(["Repository", "Tag", "Published line", "Kind"],
                         [[n["repo"], n["tag"], n["line"].replace("|", "\\|"), n["kind"]] for n in noise_all])
hash_rows = [[o["repo"], o["tag"], f"#{o['pr']}", ", ".join(o["published_by_hash"])] for o in omissions if o["published_by_hash"]]
T["P3_HASH"] = md_table(["Repository", "Tag", "PR", "Published commit"], hash_rows)

# cliff re-run reproduction
repro = collections.Counter()
diffs = []
for x in p3_rel:
    a = x["cliff_rerun"]["as_published"]
    same = a["items"] == x["list_items"] and a["prs"] == sorted(set(x["published_prs"]))
    repro["same" if same else "different"] += 1
    if not same:
        diffs.append(f"{x['repo']} {x['tag']} (published source: {x['published_source']}; re-run items {a['items']})")
T["P3_REPRO_VERSION"] = subprocess.run(["git-cliff", "--version"], capture_output=True, text=True).stdout.strip().split()[-1]
T["P3_REPRO"] = f"{repro['same']} of {sum(repro.values())} identical; different: " + "; ".join(diffs)

# Highlights: manual sample (reviewer judgement) and claim-term check
sample = {
    ("pensa-grex", "v1.0.0"): {"covered": [1, 4, 5, 6, 7, 8, 10, 13, 14, 16, 20, 21, 22, 23, 24, 25, 26, 28], "loose": [16, 20]},
    ("smalt-mcp", "v1.0.0"): {"covered": [17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29], "loose": []},
    ("ebony-enriching", "v0.1.0"): {"covered": [1, 2, 3, 4, 6], "loose": []},
    ("paper-boxing", "v0.1.0"): {"covered": [1, 2, 3, 4, 6], "loose": []},
    ("conception-space", "v0.8.5"): {"covered": [21, 22, 23], "loose": []},
    ("deco-assaying", "v0.3.2"): {"covered": [14, 15], "loose": []},
    ("flint-slating", "v0.1.5"): {"covered": [6, 7], "loose": []},
    ("smalt-mcp", "v0.2.0"): {"covered": [6, 7], "loose": []},
}
terms = {
    ("pensa-grex", "v1.0.0"): 15, ("smalt-mcp", "v1.0.0"): 15, ("ebony-enriching", "v0.1.0"): 11,
    ("paper-boxing", "v0.1.0"): 11, ("deco-assaying", "v0.3.2"): 6, ("conception-space", "v0.8.5"): 6,
    ("flint-slating", "v0.1.5"): 6, ("smalt-mcp", "v0.2.0"): 8,
}
hrows, hs = [], []
for (r, t), s in sample.items():
    x = next(x for x in p3_rel if x["repo"] == r and x["tag"] == t)
    om = [o["pr"] for o in x["omitted"]]
    notcov = [n for n in om if n not in s["covered"]]
    hrows.append([r, t, len(om), len(s["covered"]), len(s["loose"]), ", ".join(f"#{n}" for n in notcov), terms[(r, t)]])
    hs.append({"repo": r, "tag": t, "omitted": om, "covered_by_highlights": s["covered"], "loose": s["loose"],
               "not_covered": notcov, "claim_terms_checked": terms[(r, t)], "claim_terms_unsupported": 0,
               "highlights": x["highlights"]})
hrows.append(["Total", "", sum(r_[2] for r_ in hrows), sum(r_[3] for r_ in hrows), sum(r_[4] for r_ in hrows), "",
              sum(r_[6] for r_ in hrows)])
T["P3_HIGHLIGHTS"] = md_table(["Repository", "Tag", "Omitted from the list", "Described in Highlights",
                               "of which loosely", "Not described", "Claim terms checked (all found in the log)"], hrows)

ev["part3"] = {
    "definition": {"published": "GitHub Release body where the tag has a Release, else the tag's section of CHANGELOG.md on origin/main",
                   "list_line": "a line beginning '- ' or '* ' under a heading other than Highlights",
                   "published_by_number": "a list line carrying '(#N)'",
                   "omitted": "expected pull requests (truth less carriers) with no list line carrying their number",
                   "cause_order": CAUSES},
    "per_repository": [dict(zip(["repo", "tags", "github_release", "changelog_section_only", "neither",
                                 "tags_with_no_list", "expected", "published_by_number", "omitted", "omitted_but_published_by_hash",
                                 "noise_release_job_changelog_commit", "noise_change_without_pull_request"], row)) for row in p3_repo],
    "causes_by_repository": {r: dict(v) for r, v in cause_by_repo.items()},
    "cause_totals": {k: tc.get(k, 0) for k in CAUSES},
    "mechanisms": dict(mech),
    "cause_by_merge_kind": {f"{k[0]} | {k[1]}": v for k, v in xt.items()},
    "omissions": omissions,
    "noise": noise_all,
    "git_cliff_rerun_reproduction": {"identical": repro["same"], "different": diffs,
                                     "git_cliff_version": subprocess.run(["git-cliff", "--version"], capture_output=True, text=True).stdout.strip()},
    "per_release": p3_rel,
    "highlights": {
        "mechanism": "scripts/generate_changelog.py at every tag that carries it: Highlights input is git log prev..tag (git log tag for a first release), subjects and bodies, capped at MAX_LOG_CHARS = 50_000; the list is git-cliff over prev..tag, or ..tag for a first release",
        "artefacts_with_highlights": sum(1 for x in p3_rel if x["highlights"]),
        "placeholders": 0, "paragraphs_citing_a_pull_request_number": 0,
        "truncated_inputs": [{"repo": "smalt-mcp", "tag": "v1.0.0", "log_chars": 55580,
                              "note": "C-1 (#16) text starts at character 52076, beyond the cap; the Highlights paragraph does not describe #16"}],
        "sample": hs,
    },
}

# ------------------------------------------------------------------ part four
syn = SYN["main_scenario"]
ev["part4"] = {
    "main_scenario": {"checks": syn["checks"],
                      "runs": [{"tag": r_["tag"], "truth": r_["truth"], "expected": r_["expected"],
                                "listed": r_["result"]["listed"], "section": r_["result"]["section"],
                                "bookkeeping": r_["result"]["bookkeeping"], "direct_commits": r_["result"]["direct_commits"],
                                "carriers": r_["result"]["carriers"], "already_shipped": r_["result"]["already_shipped"],
                                "absorbed": r_["result"]["absorbed"], "warnings": r_["result"]["warnings"]} for r_ in syn["runs"]]},
    "extra_scenario": {"runs": [{"tag": r_["tag"], "truth": r_["truth"], "expected": r_["expected"],
                                 "listed": r_["result"]["listed"], "section": r_["result"]["section"],
                                 "bookkeeping": r_["result"]["bookkeeping"], "direct_commits": r_["result"]["direct_commits"],
                                 "already_shipped": r_["result"]["already_shipped"], "absorbed": r_["result"]["absorbed"],
                                 "warnings": r_["result"]["warnings"]} for r_ in SYN["extra_scenario"]["runs"]]},
}
for i, r_ in enumerate(syn["runs"]):
    T[f"P4_MAIN_{i}"] = r_["result"]["section"]
for i, r_ in enumerate(SYN["extra_scenario"]["runs"]):
    T[f"P4_EXTRA_{i}"] = r_["result"]["section"]
T["P4_GRAPH"] = subprocess.run(["git", "-C", str(HERE / "synthetic" / "main-scenario"), "log", "--graph", "--all",
                                "--format=%h %cn | %s%d"], capture_output=True, text=True).stdout.rstrip()
T["P4_GRAPH_EXTRA"] = subprocess.run(["git", "-C", str(HERE / "synthetic" / "extra-scenario"), "log", "--graph", "--all",
                                      "--format=%h %cn | %s%d"], capture_output=True, text=True).stdout.rstrip()
T["P4_MAIN_BOOK"] = "\n".join(f"- {r_['tag']}: " + "; ".join(f"`{b['sha'][:7]}` {b['subject']} ({b['reason'].split(':')[0]})"
                                                          for b in r_["result"]["bookkeeping"]) for r_ in syn["runs"])

import decisions as DEC  # noqa: E402
ev["part1"] = {"script": str(HERE / "proposed_list2.py"),
               "usage": "proposed_list2.py <repo_dir> <prev_tag or -> <tag> <prs.json> [--markdown]",
               "api_use": DEC.API_USE, "decisions": DEC.DECISIONS}
ev["corrections_to_earlier_figures"] = DEC.CORRECTIONS
ev["method"] = {
    "clones": "full clones (not blobless) of the ten repositories under revise/clones, fetched 2026-09-17",
    "pull_requests": "gh pr list -R ParkviewLab/<repo> --state merged --limit 1000 --json number,title,body,mergeCommit,baseRefName,headRefName,mergedAt (231 merged pull requests)",
    "releases": "gh release list and gh release view <tag> --json body for the 50 tags with a Release; CHANGELOG.md from origin/main",
    "tags": "every tag matching ^v[0-9]+\\.[0-9]+\\.[0-9]+$, sorted by version (81)",
    "scripts": ["proposed_list2.py", "measure2.py", "cliff_rerun.py", "build_synthetic.py", "report.py", "decisions.py"],
}
T["DECISIONS"] = "\n\n".join(f"{d['id']} ({d['rule']}). {d['question']} Decision: {d['decision']} Evidence: {d['evidence']}" for d in DEC.DECISIONS)
T["CORRECTIONS"] = "\n".join(f"- {c}" for c in DEC.CORRECTIONS)
T["API_USE"] = "\n".join(f"- {x}" for x in DEC.API_USE["github_api"]) + "\n\nFrom git alone: " + DEC.API_USE["git_alone"][0]
ev["summary"] = {
    "tags": tot2["tags"], "tags_with_github_release": tot3["release"], "tags_with_changelog_section_only": tot3["changelog-main"],
    "tags_with_neither": tot3["none"], "commits_in_ranges": tot2["commits"], "truth": tot2["truth"], "carriers": tot2["carriers"],
    "expected": tot2["expected"], "listed": tot2["listed"], "releases_exact": tot2["exact"],
    "releases_explained_nonexact": tot2["explained_nonexact"], "releases_unexplained": tot2["tags"] - tot2["exact"] - tot2["explained_nonexact"],
    "direct_commits": tot2["direct"], "bookkeeping_commits": tot2["bookkeeping"], "absorbed_commits": tot2["absorbed"],
    "published_by_number": tot3["published_by_number"], "omitted": tot3["omitted"], "omitted_but_published_by_hash": tot3["by_hash"],
    "omission_causes": {k: tc.get(k, 0) for k in CAUSES}, "omission_mechanisms": dict(mech),
    "noise_release_job_changelog_commit": tot3["noise:release-job changelog commit"],
    "noise_change_without_pull_request": tot3["noise:real change without a pull request"],
    "git_cliff_rerun_identical_tags": repro["same"],
    "highlights_sample": {"releases": 8, "omitted_prs": 70, "described": 49, "loosely": 2, "claim_terms_checked": 78, "claim_terms_unsupported": 0},
    "synthetic_main_scenario_matches": all(c["match"] for c in syn["checks"]),
}
json.dump(ev, open(HERE / "evidence2.json", "w"), indent=1)
json.dump(T, open(HERE / "tables.json", "w"), indent=1)
tmpl = HERE / "measure_template.md"
if tmpl.exists():
    text = tmpl.read_text()
    for k, v in T.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z0-9_]+\}\}", text)
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    (HERE / "measure.md").write_text(text)
print(json.dumps({k: v for k, v in tot2.items()}, indent=0))
print(json.dumps({k: v for k, v in tot3.items()}, indent=0))
print(dict(tc)); print(dict(mech)); print(T["P3_REPRO"]); print(T["P3_FIRST"]); print(T["P3_HIGHLIGHTS"]); print(T["P3_XTAB"]); print(T["P2_BOOK"])
