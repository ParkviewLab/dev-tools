# SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The acceptance run of scripts/generate-changelog against the measured releases.

Usage (from the root of a dev-tools checkout, which supplies the script):

    python3 tests/acceptance/acceptance.py full [--work DIR] [--report FILE]
    python3 tests/acceptance/acceptance.py tag --clone DIR --tag vX.Y.Z [--report FILE]
    python3 tests/acceptance/acceptance.py release-check --clone DIR --tag vX.Y.Z --report FILE

It needs the network and gh logged in to GitHub, which is why it is not a unit
test and is not run in CI. It never calls the model: the script runs without
ANTHROPIC_API_KEY, so every Highlights paragraph is the placeholder, and what is
compared is the list.

full
    Clones the ten repositories of the measurement into --work (default: a new
    temporary directory; a clone already there is fetched instead), runs the
    script's generate mode for every vX.Y.Z tag of each, and compares:

    - a tag the measurement recorded: the list with the recorded list, which is
      the "section" of evidence/evidence2.json (part2.per_release). They must be
      equal, except where a ruling changed the rule since the measurement; each
      such difference is written out in RULED below, with its ruling;
    - a tag released after the measurement: the pull requests listed with the
      expected set, computed by the measurement's method but with the carriers
      as ruling 9a defines them: the pull requests whose merge commit, as GitHub
      records it, lies in the release's range, less those from the repository
      itself whose head branch is develop, main or back-merge-vX.Y.Z.

    Writes the report (default: acceptance-report.md in --work) and exits 0
    when every tag passes and every recorded tag exists, 1 when a tag's list
    differs from its basis, the script fails on a tag or a recorded tag is
    missing, and 2 on bad arguments or when the run cannot go on (gh not on
    PATH, or a git or gh command failing), in which case it writes no report.

tag
    The same comparison for one tag of one clone: a disposable full clone,
    since the script writes release-body.md at the clone's root. Prints PASS or
    the differences, and writes them to --report when given.

release-check
    For a published tag: that comparison; the list and the Highlights paragraph
    of the tag's GitHub Release; the tag's section of CHANGELOG.md on main; and
    the release run's jobs in the order they ran, its attempt and the
    generate-changelog job summary found in the changelog job's log. The clone
    is fetched first, since the release job commits to main after the tag. All
    of it is written to --report, from which a reader judges the release's notes
    by the criteria in tests/acceptance/README.md.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / "scripts" / "generate-changelog"
EVIDENCE = HERE / "evidence" / "evidence2.json"
ORG = "ParkviewLab"
REPOS = (
    "pensa-grex",
    "deco-assaying",
    "smalt-mcp",
    "ebony-enriching",
    "conception-space",
    "flint-slating",
    "jonobones",
    "paper-boxing",
    "cobalt-grinding",
    "cogrind-workshop",
)
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
REMOTE_RE = re.compile(r"github\.com[:/](?P<owner>[^/:]+)/(?P<name>[^/]+?)(?:\.git)?/?$")
BACK_MERGE_HEAD = re.compile(r"^back-merge-v[0-9]+\.[0-9]+\.[0-9]+$")
PR_LINE = re.compile(r"\(#(\d+)\)$")
PR_ANY = re.compile(r"\(#(\d+)\)")
HASH_LINE = re.compile(r"\(([0-9a-f]{7,40})\)$")
SCRIPT_PLACEHOLDER = "_Highlights were not generated for this release._"
OLD_PLACEHOLDER = "_Highlights generation"  # the retired generator's placeholders began so
SUMMARY_GROUP = "generate-changelog job summary"

# Differences from the recording that a ruling made, keyed by repository and tag:
# the list as the rule now gives it, and the ruling that changed it, each ruling
# recorded, with its date and reason, under Decided in README.md.
RULED = {
    ("cogrind-workshop", "v0.1.0"): (
        "### Maintenance\n\n"
        "- Bump action pins to Node 24 (#1)\n"
        "- Adopt ParkviewLab handbook onboarding (CI, AI pointers, ty, .python-version) (#2)\n\n"
        "### Direct commits\n\n"
        "- Initial public release — cogrind-workshop (AGPL-3.0-or-later) (8208257)",
        "ruling 9a of 2026-09-18 (D9; tests/acceptance/README.md, Decided): a carrier is recognised "
        "by head branch alone, from the repository itself, so #1, a real change from "
        "ci-node24-action-pins into main, is listed under Maintenance, and its commit 958c3f5 no "
        "longer appears under Direct commits",
    ),
}


class Failure(Exception):
    """The run cannot go on (exit status 2)."""


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, errors="replace", check=False)
    if check and p.returncode != 0:
        raise Failure(f"{' '.join(cmd)} failed ({p.returncode}): {p.stderr.strip() or p.stdout.strip()}")
    return p


def git(clone: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-C", str(clone), "-c", "log.showSignature=false", *args], check=check).stdout


def version_key(tag: str) -> tuple[int, int, int]:
    m = TAG_RE.match(tag)
    return (int(m[1]), int(m[2]), int(m[3])) if m else (-1, -1, -1)


def tags_of(clone: Path) -> list[str]:
    return sorted((t for t in git(clone, "tag", "--list", "v*").split() if TAG_RE.match(t)), key=version_key)


def slug_of(clone: Path) -> str:
    m = REMOTE_RE.search(git(clone, "remote", "get-url", "origin").strip())
    if not m:
        raise Failure(f"{clone}: origin is not a github.com remote")
    return f"{m['owner']}/{m['name']}"


def recorded() -> dict[tuple[str, str], dict]:
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    return {(r["repo"], r["tag"]): r for r in data["part2"]["per_release"]}


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #


def gh_json_pages(path: str) -> list:
    """GET a paginated REST list through gh; gh prints one JSON array per page."""
    out = run(["gh", "api", "--paginate", path]).stdout
    decoder, items, i = json.JSONDecoder(), [], 0
    while True:
        while i < len(out) and out[i].isspace():
            i += 1
        if i >= len(out):
            return items
        try:
            page, i = decoder.raw_decode(out, i)
        except json.JSONDecodeError as e:
            raise Failure(f"gh api --paginate {path} did not return JSON: {e}") from None
        items.extend(page)


@dataclass(frozen=True)
class Merged:
    number: int
    title: str
    merge_commit: str | None
    head: str
    same_repository: bool


def merged_pull_requests(slug: str) -> dict[int, Merged]:
    prs = {}
    for obj in gh_json_pages(f"repos/{slug}/pulls?state=closed&per_page=100"):
        if not obj.get("merged_at"):
            continue
        head, base = obj.get("head") or {}, obj.get("base") or {}
        head_repo = (head.get("repo") or {}).get("full_name") or ""
        base_repo = (base.get("repo") or {}).get("full_name") or ""
        prs[obj["number"]] = Merged(
            obj["number"],
            obj.get("title") or "",
            obj.get("merge_commit_sha"),
            head.get("ref") or "",
            bool(head_repo) and head_repo.lower() == base_repo.lower(),
        )
    return prs


def is_carrier(pr: Merged) -> bool:
    return pr.same_repository and (pr.head in ("develop", "main") or bool(BACK_MERGE_HEAD.match(pr.head)))


def expected_set(clone: Path, prs: dict[int, Merged], prev: str | None, tag: str) -> tuple[list[int], list[int]]:
    """(expected, carriers): the pull requests whose recorded merge commit is in the range, less the carriers."""
    spec = f"refs/tags/{prev}..refs/tags/{tag}" if prev else f"refs/tags/{tag}"
    rng = set(git(clone, "rev-list", spec).split())
    truth = sorted(n for n, pr in prs.items() if pr.merge_commit in rng)
    carriers = [n for n in truth if is_carrier(prs[n])]
    return [n for n in truth if n not in carriers], carriers


# --------------------------------------------------------------------------- #
# Running the script and reading a section
# --------------------------------------------------------------------------- #


@dataclass
class ScriptRun:
    returncode: int
    stdout: str
    stderr: str
    body: str
    seconds: float


def run_script(clone: Path, tag: str) -> ScriptRun:
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "GITHUB_ACTIONS", "GITHUB_REF")}
    with tempfile.TemporaryDirectory(prefix="gc-acceptance-") as tmp:
        env["GITHUB_STEP_SUMMARY"] = str(Path(tmp) / "summary.md")
        body_path = clone / "release-body.md"
        body_path.unlink(missing_ok=True)
        start = time.monotonic()
        p = run([sys.executable, str(SCRIPT), "--mode=generate", "--tag", tag, "--repo", str(clone)], env=env, check=False)
        seconds = time.monotonic() - start
    body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
    return ScriptRun(p.returncode, p.stdout, p.stderr, body, seconds)


def split_section(text: str) -> tuple[str, str]:
    """(Highlights paragraph, list) of a section; the list starts at the first "### "
    heading after the Highlights, or at "_No changes._"."""
    lines = text.rstrip("\n").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "### Highlights") + 1
    except StopIteration:
        start = next((i + 1 for i, ln in enumerate(lines) if ln.startswith("## ")), 0)
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("### ") or lines[i].strip() == "_No changes._"),
        len(lines),
    )
    return "\n".join(lines[start:end]).strip(), "\n".join(lines[end:]).strip()


def line_numbers(line: str) -> list[int]:
    """The pull requests a list line names: the "(#N)" that ends it, as the script writes
    it, else every "(#N)" in it, as the measurement counted a published line (the retired
    generator wrote "title (#N) (hash)")."""
    m = PR_LINE.search(line.rstrip())
    return [int(m[1])] if m else [int(n) for n in PR_ANY.findall(line)]


def listed_numbers(listing: str) -> list[int]:
    """The pull requests of a list: its "- " or "* " lines under any heading but Direct commits."""
    numbers, heading = set(), None
    for line in listing.splitlines():
        if line.startswith("#"):
            heading = line.strip("# ").strip()
        elif line.startswith(("- ", "* ")) and heading not in ("Direct commits", "Highlights"):
            numbers.update(line_numbers(line))
    return sorted(numbers)


def unspan(text: str) -> str:
    """The text inside a Markdown code span that makes up the whole of text, as the
    script writes a warning into its report; any other text as it is."""
    m = re.fullmatch(r"(`+) (.*) \1", text)
    return m[2] if m else text


def summary_block(stdout: str, title: str) -> list[str]:
    """The lines under "### <title>" in the script's printed report."""
    lines, on = [], False
    for line in stdout.splitlines():
        if line.startswith("### "):
            on = line[4:].strip() == title
        elif on and line.startswith("- ") and line != "- none":
            lines.append(line[2:])
    return lines


def diff(expected: str, got: str, a: str, b: str) -> str:
    return "\n".join(difflib.unified_diff(expected.splitlines(), got.splitlines(), a, b, lineterm=""))


# --------------------------------------------------------------------------- #
# One tag
# --------------------------------------------------------------------------- #


@dataclass
class TagResult:
    repo: str
    tag: str
    basis: str  # "recorded", "ruled" or "expected set"
    passed: bool
    listing: str = ""
    detail: str = ""
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0


def check_tag(clone: Path, repo: str, tag: str, record: dict | None, prs: dict[int, Merged] | None) -> TagResult:
    """Run the script for one tag and compare its list with its basis."""
    result = run_script(clone, tag)
    if result.returncode != 0:
        return TagResult(repo, tag, "script", False, detail=f"the script exited {result.returncode}:\n{result.stderr.strip()}")
    _, listing = split_section(result.body)
    warnings = [
        w for w in map(unspan, summary_block(result.stdout, "Warnings")) if not w.startswith("ANTHROPIC_API_KEY is not set")
    ]
    out = TagResult(repo, tag, "", False, listing=listing, warnings=warnings, seconds=result.seconds)
    if (repo, tag) in RULED:
        want, ruling = RULED[(repo, tag)]
        out.basis = "ruled"
        out.passed = listing == want
        recorded_listing = record["section"] if record else "(not recorded)"
        out.detail = f"Ruled change: {ruling}.\n\nDiff from the recording to the list now:\n\n" + diff(
            recorded_listing, listing, "recorded", "now"
        )
        if not out.passed:
            out.detail += "\n\nDiff from the list as ruled to the list now:\n\n" + diff(want, listing, "as ruled", "now")
        return out
    if record is not None:
        out.basis = "recorded"
        out.passed = listing == record["section"]
        if not out.passed:
            out.detail = diff(record["section"], listing, "recorded", "now")
        return out
    out.basis = "expected set"
    if prs is None:
        prs = merged_pull_requests(slug_of(clone))
    earlier = [t for t in tags_of(clone) if version_key(t) < version_key(tag)]
    expected, carriers = expected_set(clone, prs, earlier[-1] if earlier else None, tag)
    got = listed_numbers(listing)
    out.passed = got == expected
    out.detail = (
        f"Expected set: {', '.join(f'#{n}' for n in expected) or 'none'}"
        f" (carriers left out: {', '.join(f'#{n}' for n in carriers) or 'none'}); "
        f"listed: {', '.join(f'#{n}' for n in got) or 'none'}."
    )
    return out


# --------------------------------------------------------------------------- #
# The modes
# --------------------------------------------------------------------------- #


def fresh_clone(work: Path, repo: str) -> Path:
    clone = work / repo
    if (clone / ".git").exists():
        git(clone, "fetch", "--quiet", "--force", "--prune", "--prune-tags", "origin")
    else:
        run(["gh", "repo", "clone", f"{ORG}/{repo}", str(clone), "--", "--quiet"])
    return clone


def dev_tools_state() -> str:
    head = git(HERE.parents[1], "rev-parse", "--short=10", "HEAD").strip()
    dirty = " (with uncommitted changes)" if git(HERE.parents[1], "status", "--porcelain").strip() else ""
    version = (HERE.parents[1] / "VERSION.txt").read_text(encoding="utf-8").strip()
    return f"dev-tools {version} at {head}{dirty}"


def result_line(r: TagResult) -> str:
    verdict = "pass" if r.passed else "DIFFERS"
    extra = f"; {len(r.warnings)} warnings" if r.warnings else ""
    return f"| {r.repo} | {r.tag} | {r.basis} | {verdict} | {r.seconds:.1f} s{extra} |"


def full(args: argparse.Namespace) -> int:
    work = Path(args.work).resolve() if args.work else Path(tempfile.mkdtemp(prefix="gc-acceptance-work-"))
    work.mkdir(parents=True, exist_ok=True)
    report = Path(args.report).resolve() if args.report else work / "acceptance-report.md"
    records = recorded()
    results: list[TagResult] = []
    missing: list[str] = []
    started = time.monotonic()
    for repo in REPOS:
        clone = fresh_clone(work, repo)
        prs = merged_pull_requests(slug_of(clone))
        tags = tags_of(clone)
        for key in sorted((k for k in records if k[0] == repo), key=lambda k: version_key(k[1])):
            if key[1] not in tags:
                missing.append(f"{repo} {key[1]}")
        for tag in tags:
            r = check_tag(clone, repo, tag, records.get((repo, tag)), prs)
            results.append(r)
            print(f"{repo} {tag}: {'pass' if r.passed else 'DIFFERS'} ({r.basis})", flush=True)
    elapsed = time.monotonic() - started
    by = {basis: [r for r in results if r.basis == basis] for basis in ("recorded", "ruled", "expected set", "script")}
    failed = [r for r in results if not r.passed]
    lines = [
        "# generate-changelog acceptance run",
        "",
        f"- Run: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}, {elapsed:.0f} s, from {dev_tools_state()}",
        f"- Script: `{SCRIPT}`; clones in `{work}`",
        f"- Recorded tags reproduced exactly: {sum(r.passed for r in by['recorded'])} of {len(by['recorded'])}",
        f"- Ruled differences as ruled: {sum(r.passed for r in by['ruled'])} of {len(by['ruled'])}",
        f"- Tags after the measurement listing exactly the expected set: "
        f"{sum(r.passed for r in by['expected set'])} of {len(by['expected set'])}",
        f"- Script failures: {len(by['script'])}",
        f"- Recorded tags missing from the clones: {', '.join(missing) or 'none'}",
        f"- Verdict: {'PASS' if not failed and not missing else 'FAIL'}",
        "",
        "## Every tag",
        "",
        "| Repository | Tag | Basis | Result | Time |",
        "|---|---|---|---|---|",
        *[result_line(r) for r in results],
    ]
    if failed:
        lines += ["", "## Differences", ""]
        for r in failed:
            lines += [f"### {r.repo} {r.tag} ({r.basis})", "", "```diff" if r.basis != "expected set" else "```", r.detail, "```", ""]
    lines += ["", "## Ruled differences", ""]
    for r in by["ruled"]:
        lines += [f"### {r.repo} {r.tag}: {'as ruled' if r.passed else 'NOT as ruled'}", "", "```diff", r.detail, "```", ""]
    lines += ["", "## Tags after the measurement", ""]
    for r in by["expected set"]:
        lines += [f"### {r.repo} {r.tag}: {'pass' if r.passed else 'DIFFERS'}", "", r.detail, "", "```markdown", r.listing, "```", ""]
    warned = [r for r in results if r.warnings]
    lines += ["", "## Warnings the script gave (besides the missing model key)", ""]
    lines += [f"- {r.repo} {r.tag}: {w}" for r in warned for w in r.warnings] or ["- none"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {report}")
    return 0 if not failed and not missing else 1


def one_tag(args: argparse.Namespace) -> int:
    clone = Path(args.clone).resolve()
    repo = slug_of(clone).split("/", 1)[1]
    r = check_tag(clone, repo, args.tag, recorded().get((repo, args.tag)), None)
    text = (
        f"# {repo} {args.tag}: {'PASS' if r.passed else 'DIFFERS'} (basis: {r.basis})\n\n"
        + (f"{r.detail}\n\n" if r.detail else "")
        + f"```markdown\n{r.listing}\n```\n"
        + ("".join(f"\nwarning: {w}" for w in r.warnings) + "\n" if r.warnings else "")
    )
    print(text, end="")
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
        print(f"report: {Path(args.report).resolve()}")
    return 0 if r.passed else 1


def release_runs(slug: str, tag: str) -> list[dict]:
    fields = "databaseId,workflowName,headBranch,event,status,conclusion,attempt,createdAt,url"
    runs = json.loads(
        run(["gh", "run", "list", "-R", slug, "--branch", tag, "--event", "push", "--limit", "20", "--json", fields]).stdout
    )
    return [r for r in runs if r.get("headBranch") == tag]


def job_log(slug: str, job_id: int) -> str:
    p = run(["gh", "api", f"repos/{slug}/actions/jobs/{job_id}/logs"], check=False)
    return p.stdout if p.returncode == 0 else ""


def summary_from_log(log: str) -> str | None:
    """The report the script prints between ::group:: markers, as the runner logs them."""
    out, on = [], False
    for raw in log.splitlines():
        line = re.sub(r"^\d{4}-\d\d-\d\dT[0-9:.]+Z ", "", raw)
        if f"##[group]{SUMMARY_GROUP}" in line:
            on = True
            continue
        if on and "##[endgroup]" in line:
            break
        if on and not re.fullmatch(r"::(stop-commands::)?[0-9a-f]{32}(::)?", line.strip()):
            out.append(line)
    return "\n".join(out).strip() if on else None


def release_check(args: argparse.Namespace) -> int:
    clone = Path(args.clone).resolve()
    slug = slug_of(clone)
    repo = slug.split("/", 1)[1]
    tag = args.tag
    git(clone, "fetch", "--quiet", "--force", "--prune", "--prune-tags", "origin")
    prs = merged_pull_requests(slug)
    r = check_tag(clone, repo, tag, recorded().get((repo, tag)), prs)
    earlier = [t for t in tags_of(clone) if version_key(t) < version_key(tag)]
    expected, carriers = expected_set(clone, prs, earlier[-1] if earlier else None, tag)
    now = run_script(clone, tag)  # the script's own report, for its bookkeeping and direct commits
    bookkeeping = {b.split(" ", 1)[0] for b in summary_block(now.stdout, "Bookkeeping")}
    direct = {d.split(" ", 1)[0] for d in summary_block(now.stdout, "Direct commits")}

    lines = [
        f"# Release check: {slug} {tag}",
        "",
        f"- Checked: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}, from {dev_tools_state()}",
        f"- Expected set: {', '.join(f'#{n}' for n in expected) or 'none'} "
        f"(carriers left out: {', '.join(f'#{n}' for n in carriers) or 'none'})",
        "",
        "## The script's list now, against its basis",
        "",
        f"Basis: {r.basis}. Result: {'pass' if r.passed else 'DIFFERS'}.",
        "",
        *(["```", r.detail, "```", ""] if r.detail else []),
        "```markdown",
        r.listing,
        "```",
        "",
    ]

    # The GitHub Release.
    rel = run(["gh", "release", "view", tag, "-R", slug, "--json", "body,name,url,createdAt,isDraft"], check=False)
    lines += ["## The GitHub Release", ""]
    body = None
    if rel.returncode != 0:
        lines += [f"No Release for {tag}: {rel.stderr.strip()}", ""]
    else:
        info = json.loads(rel.stdout)
        body = info.get("body") or ""
        paragraph, listing = split_section(body)
        published = listed_numbers(listing)
        lines += [
            f"- {info.get('url')}, created {info.get('createdAt')}, draft: {info.get('isDraft')}",
            f"- Pull requests listed: {', '.join(f'#{n}' for n in published) or 'none'}; "
            f"{'equal to' if published == expected else 'NOT equal to'} the expected set",
            f"- The list {'equals' if listing == r.listing else 'differs from'} the script's list now",
            f"- Highlights: {'missing' if not paragraph else 'the placeholder' if paragraph.startswith((SCRIPT_PLACEHOLDER, OLD_PLACEHOLDER)) else 'present, not a placeholder'}",
            "",
            "Each published list line:",
            "",
        ]
        heading = None
        for line in listing.splitlines():
            if line.startswith("#"):
                heading = line.strip("# ").strip()
                continue
            if not line.startswith(("- ", "* ")):
                continue
            numbers, h = line_numbers(line), HASH_LINE.search(line.rstrip())
            if numbers and heading != "Direct commits":
                what = ", ".join(
                    f"#{n}, a pull request {'of' if n in expected else 'NOT in'} the expected set" for n in numbers
                )
            elif h:
                short = h[1][:7]
                what = (
                    "a BOOKKEEPING commit" if short in bookkeeping
                    else "a direct commit of the range" if short in direct
                    else "a commit the script does not list"
                )
            else:
                what = "not a pull request or a commit"
            lines.append(f"- `{line}`: {what}")
        lines += ["", "The body:", "", "```markdown", body.rstrip(), "```", ""]

    # CHANGELOG.md on main.
    changelog = git(clone, "cat-file", "blob", "refs/remotes/origin/main:CHANGELOG.md", check=False)
    section_re = re.compile(rf"^## \[?{re.escape(tag)}\]?(\s|$)")
    count = sum(1 for ln in changelog.splitlines() if section_re.match(ln))
    section = ""
    if count:
        cl = changelog.splitlines()
        start = next(i for i, ln in enumerate(cl) if section_re.match(ln))
        end = next((j for j in range(start + 1, len(cl)) if cl[j].startswith("## ")), len(cl))
        section = "\n".join(cl[start:end]).rstrip()
    lines += [
        "## CHANGELOG.md on main",
        "",
        f"- Sections for {tag}: {count}",
        *(
            [f"- The section {'equals' if section.strip() == body.strip() else 'differs from'} the Release body"]
            if count and body is not None
            else []
        ),
        "",
        "```markdown",
        section or "(none)",
        "```",
        "",
    ]

    # The release run.
    lines += ["## The release run", ""]
    runs = release_runs(slug, tag)
    if not runs:
        lines += [f"No workflow run found for a push of {tag}.", ""]
    for wr in runs:
        view = json.loads(
            run(["gh", "run", "view", str(wr["databaseId"]), "-R", slug, "--json", "jobs,attempt,conclusion,workflowName,url"]).stdout
        )
        jobs = sorted(view.get("jobs") or [], key=lambda j: j.get("startedAt") or "")
        lines += [
            f"### {view.get('workflowName')}: {view.get('conclusion')}, attempt {view.get('attempt')}",
            "",
            f"{view.get('url')}",
            "",
            "| Job | Started | Completed | Conclusion |",
            "|---|---|---|---|",
            *[f"| {j.get('name')} | {j.get('startedAt')} | {j.get('completedAt')} | {j.get('conclusion')} |" for j in jobs],
            "",
        ]
        changelog_jobs = [j for j in jobs if j.get("name") == "changelog"]
        for cj in changelog_jobs:
            others = [j for j in jobs if j is not cj]
            after = all((j.get("completedAt") or "") <= (cj.get("startedAt") or "") for j in others)
            lines += [f"- The changelog job started after every other job had completed: {'yes' if after else 'NO'}"]
            summary = summary_from_log(job_log(slug, cj["databaseId"]))
            if summary is None:
                lines += ["- No generate-changelog job summary in the changelog job's log.", ""]
            else:
                version = re.search(r"^- dev-tools: (.+)$", summary, flags=re.MULTILINE)
                lines += [
                    f"- The job summary names dev-tools {version[1] if version else '(no version found)'}",
                    "",
                    "```markdown",
                    summary,
                    "```",
                    "",
                ]
        if not changelog_jobs:
            lines += ["- No job named changelog in this run.", ""]

    report = Path(args.report).resolve()
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The acceptance run of scripts/generate-changelog.")
    sub = parser.add_subparsers(dest="mode", required=True)
    p_full = sub.add_parser("full", help="every tag of the ten repositories")
    p_full.add_argument("--work", metavar="DIR", help="where the clones go (default: a new temporary directory)")
    p_full.add_argument("--report", metavar="FILE", help="the report (default: acceptance-report.md in --work)")
    p_tag = sub.add_parser("tag", help="one tag of one clone")
    p_tag.add_argument("--clone", required=True, metavar="DIR", help="a disposable full clone")
    p_tag.add_argument("--tag", required=True, metavar="vX.Y.Z")
    p_tag.add_argument("--report", metavar="FILE")
    p_check = sub.add_parser("release-check", help="a published tag: the comparison, the Release, CHANGELOG.md, the run")
    p_check.add_argument("--clone", required=True, metavar="DIR", help="a disposable full clone")
    p_check.add_argument("--tag", required=True, metavar="vX.Y.Z")
    p_check.add_argument("--report", required=True, metavar="FILE")
    args = parser.parse_args(argv)
    if not shutil.which("gh"):
        print("acceptance: error: gh (the GitHub CLI) is not on PATH", file=sys.stderr)
        return 2
    if getattr(args, "tag", None) and not TAG_RE.match(args.tag):
        print(f"acceptance: error: {args.tag!r} is not a vX.Y.Z tag", file=sys.stderr)
        return 2
    try:
        return {"full": full, "tag": one_tag, "release-check": release_check}[args.mode](args)
    except Failure as e:
        print(f"acceptance: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
