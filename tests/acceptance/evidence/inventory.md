# Inventory for splitting book 131: Proposal A and Proposal B

Proposal A, "One changelog generator": one script in dev-tools replaces each repository's `scripts/generate_changelog.py`, `cliff.toml` and the git-cliff install step; it builds the list from merged pull requests, lists build, chore, ci and style changes under Maintenance, lists direct commits, and may add a required check on Conventional Commit pull request titles; release workflows check dev-tools out at a pinned release tag.

Proposal B, "Real merges and the back-merge pull request": pull requests into develop are merged with real merge commits titled with the pull request's title and number; the back-merge from main into develop, and the open-cycle version bump, reach develop by a pull request from a branch named `back-merge-<tag>`; the version guard gains a back-merge mode and loses its depth-one fetch; `git-back-merge` in dev-tools performs the back-merge.

## Sources and method

Read on 2026-09-17, read-only: handbook 4b572e0 (main, v0.23.1), dev-tools 69d3e36 (main, v1.1.0), cobalt-grinding a25741c, cogrind-workshop 26d72e4, conception-space 4cc6bf0, deco-assaying a91a25a, ebony-enriching 73c4065, flint-slating fab033e, jonobones ff27c39, paper-boxing 0a98c44, pensa-forma 72b4405, pensa-grex fec0f0f, smalt-mcp d3242f3. The handbook and dev-tools were read in place from handbook-main and dev-tools-main; the eleven repositories were read from fresh blobless clones of develop (heads confirmed against `gh api …/commits/develop`). Settings were read with `gh api` GET calls. Nothing was pushed or changed.

Each hit of the search terms (squash, git-cliff, cliff, generate_changelog, changelog, back-merge, cascade, --no-ff, dev-release, open cycle, .dev0, version-guard, no-version-change, merge commit, linear, rebase, plus merge button, first-parent, bypass, up to date, Highlights, release-body) was read in context. A row appears where the line bears on A or B and must or may change; lines that bear on a proposal but need no edit are listed under "Reviewed, no change". Hits that do not bear on either proposal (CSS `linear-gradient`, database `CASCADE`, the historical bodies of CHANGELOG.md) are omitted. The quoted text is the first line of the cited range, cut at about 150 characters.

Proposal column: A, B, or A+B where one line carries both. "Only if …" in the Change column marks a row that depends on an open decision; such rows are counted with the rest.

## Counts

| Repository | Rows | A | B | A+B | Files deleted | Files changed | New files |
|---|---|---|---|---|---|---|---|
| handbook | 130 | 48 | 70 | 12 | 2 | 33 | 3 |
| dev-tools | 25 | 3 | 19 | 3 | 0 | 7 | 4 |
| cobalt-grinding | 27 | 16 | 9 | 2 | 2 | 8 | 0 |
| cogrind-workshop | 27 | 16 | 9 | 2 | 2 | 8 | 0 |
| conception-space | 26 | 14 | 11 | 1 | 2 | 9 | 0 |
| deco-assaying | 27 | 16 | 9 | 2 | 2 | 8 | 0 |
| ebony-enriching | 27 | 16 | 9 | 2 | 2 | 8 | 0 |
| flint-slating | 27 | 16 | 9 | 2 | 2 | 8 | 0 |
| jonobones | 25 | 15 | 9 | 1 | 2 | 7 | 0 |
| paper-boxing | 28 | 14 | 12 | 2 | 2 | 9 | 0 |
| pensa-forma | 18 | 7 | 10 | 1 | 2 | 6 | 0 |
| pensa-grex | 29 | 15 | 13 | 1 | 2 | 10 | 0 |
| smalt-mcp | 27 | 16 | 9 | 2 | 2 | 8 | 0 |
| Total | 443 | 212 | 198 | 33 | 24 | 129 | 7 |

| Proposal | Rows (A+B rows counted in both) | Repositories touched | Files changed | Files deleted | New files |
|---|---|---|---|---|---|
| A | 245 | 13 | 76 | 24 | 3 |
| B | 231 | 13 | 88 | 0 | 4 |

"New files" counts the planned files listed as rows (in dev-tools the tests are counted as one entry per proposal); conditional new files in the product repositories (the title workflow) are not counted.

## handbook

Read at 4b572e0 (main, v0.23.1).

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `README.md` | 21 | `` \| [commits-and-changelogs.md](docs/commits-and-changelogs.md) \| Conventional Commits, `cliff.toml`, the LLM-Highlights changelog \| `` | A | Name the shared dev-tools changelog script in place of `cliff.toml`. |
| `README.md` | 22 | `` \| [releases.md](docs/releases.md) \| Version single-source-of-truth, `git bump`/`git release`, the gate, back-merge cascade \| `` | B | "back-merge cascade" becomes the back-merge pull request. |
| `README.md` | 44 | `` - **[`templates/`](templates/)** — copy-paste sources kept identical across repos: `cliff.toml`, `pyproject.toml.template`/`package.json.template`, … `` | A | Remove `cliff.toml` and `generate_changelog.py` from the list of templates kept identical across repos. |
| `README.md` | 67 | `` This handbook is developed through the flow it prescribes. Work happens on a prefixed working branch (`doc-<topic>` for most changes) in an ephemeral … `` | B | "reviews and squash-merges it" becomes "reviews and merges it with a merge commit titled with the PR title and number". |
| `REUSE.toml` | 15 | `` path = [".github/**", "scripts/**", "templates/cliff.toml", "templates/generate_changelog.py", "templates/pyproject.toml.template", … `` | A | Remove the entries "templates/cliff.toml" and "templates/generate_changelog.py" (follows the deletion of both templates). |
| `AGENTS.md` | 14 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Generated copy of the pointer template: re-run `scripts/sync-agent-files.sh` after the template changes (line 14 says squash-merged). |
| `CLAUDE.md` | 14 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | As AGENTS.md:14 (same managed block). |
| `.github/workflows/version-guard.yml` | 3-6 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Rewrite the header: the back-merge is a PR from `back-merge-<tag>` checked by the back-merge mode, not a direct push. Byte-identical to the template; keep it so. |
| `.github/workflows/version-guard.yml` | 16-44 | `` no-version-change: `` | B | Add the back-merge mode inside the existing `no-version-change` job (keep the job id: it is the required context). Select it by head ref `back-merge-*` from this repo, not a fork. |
| `.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch; `fetch-depth: 0` already provides develop and the tags, and the shallow fetch breaks the ancestry checks the new mode needs. |
| `.github/workflows/release.yml` | 7-9 | `` # `changelog` job: a docs repo has no Conventional-Commit signal to categorise, `` | A+B | B: the generated notes will list the back-merge PR once it is a PR; A: rewrite if VERSION.txt repos adopt the shared script instead of generated notes (open decision). |
| `.github/workflows/release.yml` | 81 | `` if ! gh release create "$TAG" --title "$TAG" --verify-tag --generate-notes; then `` | B | `--generate-notes` will include "Back-merge: main → develop after vX (#N)". Either label the back-merge PR and exclude the label in a new `.github/release.yml`, or switch to the shared script (A). |
| `.github/release.yml` | new |  | B | New file only if the exclusion route is chosen: `changelog.exclude.labels` naming the label `git back-merge` applies. Covered by REUSE.toml:15 (`.github/**`). |
| `docs/northstar.md` | 24 | `` The shape is concrete. Every repo is cloned the same way, a contained layout with a bare clone and one worktree per trunk; every repo has the same … `` | A+B | B: "every pull request is squash-merged" becomes merged with a merge commit carrying its Conventional Commit title; A: "which is what the changelog is generated from" becomes "and the changelog is generated from the merged pull requests". Amend the northstar first, in the same PR. |
| `docs/northstar.md` | 56 | `` 1. **One source of truth.** A fact stated twice is a fact that will drift. Prefer one source + derivation over two copies kept in sync by discipline. … `` | A | Axiom 1: "the changelog from commits" becomes "the changelog from merged pull requests" (and direct commits). |
| `docs/northstar.md` | 62 | `` 4. **Automate the mechanical; gate the irreversible.** Changelogs and releases are scripted and verified by a CI gate — *and* merging to a shared … `` | B | Axiom 4 ("merging to a shared trunk … require an explicit human hand"): check against the ruling on who merges the back-merge PR; no edit if the release ask counts as that hand, otherwise amend. |
| `docs/northstar.html` | 213-215 | `` is squash-merged with a Conventional Commit title, which is what the `` | A+B | HTML twin of northstar.md:24; carry the same wording. |
| `docs/northstar.html` | 321 | `` <div class="axiom"><span class="big">1</span><div class="k">axiom 1</div><h4>One source of truth</h4><p>A fact stated twice is a fact that will … `` | A | HTML twin of axiom 1 (northstar.md:56). |
| `docs/northstar.html` | 324 | `` <div class="axiom"><span class="big">4</span><div class="k">axiom 4</div><h4>Automate the mechanical; gate the irreversible</h4><p>Changelogs and … `` | B | HTML twin of axiom 4; changes only if northstar.md:62 changes. |
| `docs/branching.md` | 19-34 | `` Working branches are named `<prefix>-<short-description>`, **hyphen not slash**. The prefix signals the *kind* of change. The prefixes mirror the … `` | B | Add `back-merge-` to the canonical prefix table (the branch `back-merge-<tag>` that `git back-merge` creates; hyphen, not slash, per line 21), with its title rule and "excluded from the notes". |
| `docs/branching.md` | 29-31 | `` \| `ops-` \| `chore:` / `ci:` \| _(dropped from changelog — operational/infra)_ \| `` | A | The "_(dropped)_" entries for `ops-`/`ci-`/`build-` become "Maintenance" (A lists build, chore, ci, style there). |
| `docs/branching.md` | 36 | `` > **Key rule: the PR title carries the changelog prefix, not the branch.** Branches are **squash-merged**, so the *PR title* becomes the commit … `` | A+B | B: "Branches are squash-merged, so the PR title becomes the commit subject" is replaced (merge commit titled "<PR title> (#N)"); A: `git-cliff` is gone and unprefixed titles land under "Other changes", not "silently dropped". |
| `docs/branching.md` | 54 | `` - Working branches **squash-merge** into `develop`: each PR collapses to a single commit whose subject is the PR title (the `feat:`/`fix:`/… prefix … `` | A+B | B: working branches merge into develop with a merge commit (GitHub uses --no-ff); branch commits stay in history on the second-parent side. A: drop "the prefix `git-cliff` parses". |
| `docs/branching.md` | 62 | `` - **Per feature** — `git log --first-parent develop` is one line per squash commit (one per feature) plus one back-merge commit per release, each … `` | B | "one line per squash commit … plus one back-merge commit per release … because the cascade merges main into develop with --no-ff" becomes one line per PR merge commit, one back-merge PR merge per release, and `git dev-release` dev-build commits. |
| `docs/branching.md` | 63 | `` - **Per release** — `git log --first-parent main` is one line per release merge commit. `` | B | Optional precision: main's first-parent chain also carries each release bump and changelog commit (pre-existing imprecision, touched by the same rewrite). |
| `docs/branching.md` | 68 | `` The repo is configured **squash-only** (merge-commit and rebase merges are disabled), so a PR's merge button can only squash — there's no wrong … `` | B | "configured squash-only (merge-commit and rebase merges are disabled)" becomes merge-commit-only (squash and rebase disabled). |
| `docs/branching.md` | 70 | `` - **Feature PR → `develop`:** opened by anyone (including AI devs); a **human reviews and squash-merges** it (the merge button, or `gh pr merge <n> … `` | B | "a human reviews and squash-merges it (… `gh pr merge <n> --squash`)" becomes merges it (`gh pr merge <n> --merge`); add who merges the back-merge PR per the ruling. |
| `docs/branching.md` | 75 | `` Two steps follow a merge, and they have different owners. The **sync** belongs to whoever performed the merge — the squash merge of a PR, but equally … `` | B | "the squash merge of a PR, but equally the release promotion and the back-merge, which have no PR author at all": the back-merge now has a PR and an author; only the promotion has none. |
| `docs/branching.md` | 94-107 | `` > **A squash merge breaks the ancestry test.** The squash is a *fresh* commit, so the branch tip is never an ancestor of the trunk, and `git branch … `` | B | Rewrite the cleanup: under real merges the branch tip is an ancestor of develop again. Sequence: `git fetch --prune origin`, `git merge-base --is-ancestor <branch> origin/develop`, `git worktree remove`, `git branch -d`. Drop "`-D`, not `-d`" (104) and the `git diff --stat` note (105). |
| `docs/ci.md` | 12 | `` A PR can't merge into `develop` until its required checks are green — enforced by **branch protection** (required status checks on `develop`), so the … `` | B | "the squash button stays disabled" becomes "the merge button". |
| `docs/ci.md` | 14-16 | `` - **`version guard`** — the PR didn't change the version source-of-truth; bumps happen at release on `main`, not in feature work. … `` | A+B | B (16): the version guard gains the back-merge mode (a PR from `back-merge-<tag>` must carry exactly the latest release, plus the open-cycle bump in code repos). A (if the title check is adopted): add it to the every-repo required checks. |
| `docs/ci.md` | 26 | `` **Enforcement.** Add these as **required status checks** on `develop` (Settings → Branches, or `gh api`), and **let admins bypass** — the release … `` | B | The admin bypass is no longer for the back-merge; it remains for `git dev-release` dev-build pushes. "promotion (develop→main) … direct pushes … must not be blocked by these PR checks" is already wrong: the promotion pushes main. |
| `docs/ci.md` | 30-43 | `` Configure every repo so the merge **method can't be picked wrong** — make it **squash-only**: `` | B | Recipe becomes merge-commit-only: `--enable-merge-commit=true --enable-squash-merge=false --enable-rebase-merge=false`, and `-f merge_commit_title=PR_TITLE -f merge_commit_message=PR_BODY` (or BLANK); line 38 loses "so git-cliff parses". |
| `docs/ci.md` | 45 | `` - **Squash-only** means a PR's merge button can only squash — no one can pick the wrong method for a feature PR into `develop` (see … `` | B | "Squash-only means a PR's merge button can only squash" becomes merge-commit-only. |
| `docs/ci.md` | 46 | `` - **`squash_merge_commit_title=PR_TITLE` is load-bearing.** The GitHub default (`COMMIT_OR_PR_TITLE`) uses the *commit* subject on a single-commit … `` | A+B | B: the setting that matters becomes `merge_commit_title=PR_TITLE` (title and number on the merge commit; the current MERGE_MESSAGE would title every merge "Merge pull request #N from …"). A: the changelog reads PR titles from the API, so the setting governs the first-parent ledger, not the list. |
| `docs/ci.md` | 48 | `` - Because the repo is squash-only, `develop → main` (which needs a merge commit) is done **from the CLI during a release** — `git merge --no-ff … `` | B | "Because the repo is squash-only, develop → main … is done from the CLI": the reason no longer holds; state the real reasons (one release authorisation; main takes direct pushes) or record a decision on a promotion PR. |
| `docs/ci.md` | 69-73 | `` On `pull_request` to `develop`, fails if the version source-of-truth (`pyproject.toml` `[project].version` / `package.json` `version` / … `` | B | Describe both modes of the guard. Line 73 ("A branch cut before the open-cycle fails this check") needs review: the open cycle now arrives by the back-merge PR, and (unverified) the guard reads the merge ref, so such a branch probably passes today. |
| `docs/ci.md` | 110 | `` - The `changelog` job needs `contents: write` (scoped to that job) and the org-level `ANTHROPIC_API_KEY`. It pulls the anthropic SDK just-in-time … `` | A | Changelog job: add `pull-requests: read`, the dev-tools checkout at a pinned tag, and `uv run --no-project`; keep the ANTHROPIC_API_KEY sentence while the Highlights call stays in the script. |
| `docs/ci.md` | 117 | `` The release profile for repos whose version lives in `VERSION.txt` (docs repos like this handbook, and `dev-tools`): the same three-check `gate` (tag … `` | A+B | B: generated notes will list the back-merge PR; state the exclusion. A: state whether VERSION.txt repos adopt the shared script. (Pre-existing: dev-tools has no release workflow, so "and dev-tools" is inaccurate.) |
| `docs/ci.md` | 129 | `` - **Feature PRs into `develop` must not change the version.** `version-guard.yml` fails the PR if the version source-of-truth (`pyproject.toml` … `` | B | Replace "(The release back-merge to develop is a direct push, not a PR, so it isn't subject to this.)" with the back-merge mode. |
| `docs/ci.md` | 157 | `` Cross-project scripts that encode an org convention live in **[`ParkviewLab/dev-tools`](https://github.com/ParkviewLab/dev-tools)**, not in each … `` | B | "a git pull in dev-tools propagates updates … with no re-run" holds for changed scripts only; `git-back-merge` is a new command and needs one `install.sh` run (dev-tools README:15 says so). |
| `docs/ci.md` | 161 | `` A `dev-tools` script may also run inside a repo's workflow, checked out at an exact released tag (`build-pages-site` in … `` | A | "(`build-pages-site` … is the case)": the changelog job becomes a second workflow that checks dev-tools out at a pinned tag; name it. |
| `docs/releases.md` | 71 | `` > **Sync `develop` before you promote.** `git merge --no-ff develop` merges the *local* `develop` worktree, not `origin/develop`. After a PR … `` | B | "After a PR squash-merges on GitHub" becomes "after any merge on GitHub (a feature PR or the back-merge PR)". |
| `docs/releases.md` | 75 | `` - **Choosing the bump kind:** the releaser **reviews the changes since the last release, proposes** major / minor / patch with a one-line rationale, … `` | B | Minor: "The Conventional Commit types in the range are the signal": with real merges the range holds branch commits too; the signal is the PR titles on the first-parent chain. |
| `docs/releases.md` | 78 | `` - **`VERSION.txt`-file repos** (no `pyproject`/`package.json`, e.g. this handbook): `git bump`/`git release` are **SoT-aware** — they detect … `` | A | Only if VERSION.txt repos adopt the shared script: "no `changelog` job" changes. |
| `docs/releases.md` | 89 | `` Promotion is `develop → main` done **from the CLI** with `git merge --no-ff develop` — a merge commit, so `git log --first-parent main` is a dated … `` | B | "the repo is squash-only, so this merge commit is made locally": replace the reason, as ci.md:48. |
| `docs/releases.md` | 101 | `` 4. **`changelog`** (`needs: [gate, docker, pypi]`) — runs `generate_changelog.py` `--mode=generate` against the tag (the one LLM call), switches to … `` | A | "runs `generate_changelog.py` `--mode=generate` against the tag": describe the shared dev-tools script at its pinned tag, what it reads (merged PRs in the range, direct commits, excluding release mechanics), and keep the two phases and the `docs(changelog): v<new> [skip ci]` commit. |
| `docs/releases.md` | 107 | `` **`VERSION.txt` repos diverge furthest:** [`release-txt.yml`](../templates/.github/workflows/release-txt.yml) is `gate` → `release` only. There is … `` | A+B | As ci.md:117: B, the back-merge PR in generated notes; A, adoption decision for VERSION.txt repos. |
| `docs/releases.md` | 111-119 | `` ## After the release: the back-merge cascade (mandatory) `` | B | Rename and rewrite the section: after `gh run watch` is green, `git back-merge` creates `back-merge-<tag>` from develop, merges main into it, adds the open-cycle bump in code repos, pushes, opens the PR into develop; checks run; merged with a merge commit by whoever the ruling names; then `git -C ../<repo>-develop pull --ff-only`; then develop into each open working branch. |
| `docs/releases.md` | 121-128 | `` git -C ../<repo>-develop merge --no-ff main -m "Back-merge: main → develop after $(git describe --tags --abbrev=0)" \ `` | B | Replace the command block (`merge --no-ff main -m "Back-merge: …" && … push`) with the `git back-merge` invocation and the pull after the merge. |
| `docs/releases.md` | 130 | `` `--no-ff` is deliberate. A fast-forward would move `develop` onto `main`'s tip and replace `develop`'s first-parent history with `main`'s release … `` | B | Rewrite: the back-merge PR's merge commit keeps develop's first-parent ledger; drop "-m keeps the editor closed" and "one squash commit per feature"; add the conflict fallback (resolve on the `back-merge-<tag>` branch, never on main). |
| `docs/releases.md` | 132 | `` The cascade is **manual on purpose** (a small number of commands at a moment the user is already at the keyboard; an auto-PR version was considered … `` | B | "The cascade is manual on purpose (… an auto-PR version was considered and declined)": replace with the new dated decision and its reason, so the record does not state both. |
| `docs/releases.md` | 146 | `` **2. Open the next cycle at release time (code repos).** The [back-merge cascade](#after-the-release-the-back-merge-cascade-mandatory) also bumps … `` | B | "(a direct push — exempt from version-guard.yml, like the back-merge itself)": the open-cycle bump now rides in the back-merge PR and is verified by the guard's back-merge mode; revisit the parenthetical on branches cut before the open cycle. |
| `docs/releases.md` | 148 | `` **3. Cut a dev build on demand — never per-merge.** When an engineer asks for one, `git dev-release` **asks the bump kind** (patch/minor/major) — … `` | B | `git dev-release` now fetches and refuses (or fast-forwards) unless develop equals origin/develop before it commits; its dev-build push remains a direct push under the admin bypass. |
| `docs/releases.md` | 152 | `` **`VERSION.txt` / docs repos skip the open cycle.** Nothing reads a docs repo's version between releases (no app, no package, no dev build), so … `` | B | "VERSION.txt / docs repos skip the open cycle": dev-tools opens one (develop holds 1.1.1-dev). The back-merge mode and `git back-merge` must handle the `-dev` marker; correct the sentence or dev-tools. |
| `docs/commits-and-changelogs.md` | 8 | `` ParkviewLab generates `CHANGELOG.md` and the GitHub Release notes **automatically** from commit history, using [Conventional … `` | A | "from commit history, using Conventional Commits + git-cliff + …": from merged PR titles and direct commits by the shared dev-tools script, plus the Highlights paragraph; the VERSION.txt parenthesis follows the adoption decision (and B: the back-merge PR in generated notes). |
| `docs/commits-and-changelogs.md` | 12-21 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stay in git history, not surfaced \| `` | A | Replace the table with the script's groups: Breaking changes, Features, Bug fixes, Performance, Refactor, Docs, Tests, Reverts, Maintenance (build, chore, ci, style), Other changes, Direct commits. Line 20 "_(dropped)_" and line 21 (the `Merge` / `Revert` row: "dropped / Reverts") go (release-mechanics PRs are excluded by rule, GitHub revert PRs go to Reverts). |
| `docs/commits-and-changelogs.md` | 25 | `` > **The PR title is what matters.** PRs are **squash-merged**, so the PR title becomes the commit subject `git-cliff` parses. A commit/PR without a … `` | A+B | B: "PRs are squash-merged, so the PR title becomes the commit subject"; A: "`git-cliff` parses" and "silently dropped" go; the list reads merged PR titles, and unprefixed titles land under Other changes. |
| `docs/commits-and-changelogs.md` | 27-33 | `` ## `cliff.toml` — the canonical template, copied verbatim `` | A | Replace the `cliff.toml` section with the shared script's rules (how a release's PRs are found, exclusions, bookkeeping by content, first release covers the whole history). |
| `docs/commits-and-changelogs.md` | 46-53 | `` - The categorized list below it is mechanical (git-cliff). `` | A | The example entries "(abc1234)" follow the script's entry format; line 53 "mechanical (git-cliff)" names the script. |
| `docs/commits-and-changelogs.md` | 56-67 | `` ## `generate_changelog.py` — two-phase `` | A | Replace the `generate_changelog.py` section: the shared script in dev-tools, checked out at a pinned tag, `--repo`, `--tag`, the two phases, the model pin (HIGHLIGHTS_MODEL) and the input cap (MAX_LOG_CHARS) moving with it. |
| `docs/ai-collaboration.md` | 25 | `` - **Feature PR → `develop` is the user's merge.** A human reviews and squash-merges it (the repo is squash-only, so the button can't do the wrong … `` | B | "A human reviews and squash-merges it (the repo is squash-only …)" becomes merges it with a merge commit (merge-commit-only). |
| `docs/ai-collaboration.md` | 26 | `` - **Prompt for a release after every `develop` merge.** As soon as a merge into `develop` is confirmed, proactively ask the user whether to cut a … `` | B | "Prompt for a release after every develop merge": exempt the back-merge PR (say "every merge of a working-branch PR"). |
| `docs/ai-collaboration.md` | 28 | `` - **That one release ask authorises the whole CLI flow** — including the `develop → main` promotion (`git merge --no-ff develop`), bump, tag, push, … `` | B | "… bump, tag, push, and back-merge cascade": state the ruling on whether the release ask covers `gh pr merge <n> --merge` on the back-merge PR. |
| `docs/ai-collaboration.md` | 29 | `` - **Release preflight:** before the promotion, confirm every PR that should ship is actually merged (`gh pr list --state open --base develop`), and … `` | B | Preflight: also confirm the previous back-merge PR merged (`git merge-base --is-ancestor <last tag> origin/develop`); an open back-merge PR is a blocker. |
| `docs/ai-collaboration.md` | 32 | `` - After a release, run the **back-merge cascade** ([`releases.md`](releases.md)). `` | B | "run the back-merge cascade" becomes "run `git back-merge` and merge its PR". |
| `docs/agents.md` | 50 | `` - **Only the author, the coders, and the wiki's librarian write**, and each only to its own target: the HTML twin's file, the working branch, the … `` | B | "(pushing to a trunk, merging, tagging, releasing, the back-merge cascade)": the back-merge PR and its merge. |
| `docs/agents.md` | 51 | `` - **Deterministic sequences are not agents.** Creating the prefixed worktree, `git bump`, `git release`, the cascade: a language model adds … `` | B | "`git bump`, `git release`, the cascade": the cascade becomes `git back-merge` in dev-tools. |
| `docs/new-repo-checklist.md` | 19 | `` - [ ] Configure **squash-only** merge settings (squash on; merge-commit + rebase off; `squash_merge_commit_title=PR_TITLE`; auto-delete branches). … `` | B | "Configure squash-only merge settings (…`squash_merge_commit_title=PR_TITLE`…)" becomes merge-commit-only with `merge_commit_title=PR_TITLE` and `merge_commit_message=PR_BODY` or BLANK. |
| `docs/new-repo-checklist.md` | 40-41 | `` - [ ] `cliff.toml` — copy **verbatim** from [`templates/cliff.toml`](../templates/cliff.toml). `` | A | Delete both items: a repo copies nothing for the changelog. |
| `docs/new-repo-checklist.md` | 42 | `` - [ ] Workflows from [`templates/.github/workflows/`](../templates/.github/workflows/): `reuse.yml` + `version-guard.yml` (**every** repo), plus … `` | A | Drop "`cliff.toml`, or `generate_changelog.py`" from the VERSION.txt exclusion; add the PR-title workflow to the every-repo list if adopted. |
| `docs/new-repo-checklist.md` | 43 | `` - [ ] **Branch protection on `develop`:** mark the workflow checks as **required status checks** (so the merge button waits for green); **let admins … `` | B | "let admins bypass so the release back-merge/promotion (direct pushes) aren't blocked": the bypass is for `git dev-release` pushes; the back-merge is a PR. |
| `docs/new-repo-checklist.md` | 71 | `` - [ ] Back-merge cascade `main → develop → working branches`. See [`releases.md`](releases.md). `` | B | "Back-merge cascade `main → develop → working branches`" becomes "`git back-merge`; merge its PR; pull develop; develop into open working branches". |
| `docs/electron-tooling.md` | 46 | `` - Changelog automation (`cliff.toml` + `scripts/generate_changelog.py`) is the same language-agnostic pair as everywhere else. `` | A | "(`cliff.toml` + `scripts/generate_changelog.py`) is the same language-agnostic pair": point at the shared dev-tools script; nothing is copied. |
| `docs/electron-tooling.md` | 72 | `` Between releases `develop` carries a pre-release version (see [`releases.md`](releases.md#development-versioning)). For a Node/Electron repo it must … `` | B | "Open the cycle with `git dev-release --open` right after each release": the open-cycle bump now rides in the back-merge PR made by `git back-merge`. |
| `docs/node-tooling.md` | 62 | `` - The changelog automation (`cliff.toml` + `scripts/generate_changelog.py`) is **language-agnostic**: the Python script reads `package.json` as well … `` | A | "Copy both from the handbook templates": the shared dev-tools script, checked out by the workflow. |
| `docs/docs-site.md` | 112 | `` The workflow checks `dev-tools` out at a **released tag** into `dev-tools/`, a subfolder of the checkout, and runs the command above from the repo … `` | A | "This is the one place a workflow reads another ParkviewLab repo" becomes false; name the changelog job as the second, under the same pinned-tag rule. |
| `docs/in-flight_ideas.md` | 49 | `` Decided: keep the permanent `develop`+`main` model, not release-from-main. Instead automate the back-merge cascade (a `git back-merge` dev-tool) and … `` | B | The entry is realised by `git back-merge`, but by PR, not by push; update or promote the entry when B is built. |
| `docs/in-flight_ideas.md` | 52 | `` Coverage floors + a testing-trophy note; publint/attw before npm publish; a pinned `ty`; Electron Fuses + renderer-security tripwire. [A9, A11-A15, … `` | A | Cites A11 (PR-title check); update if A adopts the check. |
| `docs/handbook-improvements_ideas.md` | 250 | `` - A11 Add a PR-title Conventional-Commit check on `develop` PRs so a mistyped prefix fails loudly instead of silently vanishing from the changelog … `` | A | A11 "Add a PR-title Conventional-Commit check": mark as adopted by A if the check lands; it must exempt the back-merge PR unless B gives that PR a Conventional title. |
| `docs/handbook-improvements_ideas.md` | 312 | `` Instead, automate that cost (P2/S-M, preserve-bespoke + augment). A `git back-merge` dev-tool runs the whole post-release tail as one command from … `` | B | D1's design ("merge it down to develop with --no-ff …, push, open the next dev cycle via … `git dev-release --open`") is superseded: branch `back-merge-<tag>`, PR, open cycle inside it. |
| `docs/handbook-improvements_ideas.md` | 316 | `` P1 (high value, low regret): A1, A2, A3, A4, A7, A8, A9, A10, A11, A13, A24, A25, B1, B2, C7a. P2: A5, A12, A14, A15, A16, A17, A18, A22, A23, A26, … `` | B | "remaining work is automating the cascade": update the status when B lands. |
| `templates/AGENTS.md.template` | 9 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | "Merging a PR into develop is the user's call": state the back-merge PR exception if the ruling makes one. |
| `templates/AGENTS.md.template` | 10 | `` - **Tagging, cutting a release, force-pushing, or pushing to a protected branch each need an explicit, per-action go-ahead** — never inferred from a … `` | B | "One release ask covers the whole CLI release flow": say whether that includes merging the back-merge PR. |
| `templates/AGENTS.md.template` | 14 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | "PRs are squash-merged, so the PR title carries the Conventional Commit prefix … the changelog is generated from" becomes merged with a merge commit titled with the PR title and number; the changelog is built from the merged PRs (A wording). |
| `templates/CLAUDE.md.template` | 9-14 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Identical to AGENTS.md.template; same edits; then re-sync every repo. |
| `templates/CONTRIBUTING.md` | 3 | `` > Template — copy to a new repo as **`docs/CONTRIBUTING.md`** (this is the path every `cliff.toml` references). Replace `<repo>` as needed. The … `` | A | Drop "(this is the path every `cliff.toml` references)"; the only reference is in the retired templates/cliff.toml. |
| `templates/CONTRIBUTING.md` | 10 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button can only squash; **merging is the maintainer's action.** `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `templates/CONTRIBUTING.md` | 11 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then bump + tag) — not a PR. See the handbook's `releases.md`. `` | B | Optional: add that the release ends with the back-merge PR from `back-merge-<tag>`. |
| `templates/CONTRIBUTING.md` | 15 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and the changelog is generated from it (via … `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `templates/CONTRIBUTING.md` | 25 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `templates/CONTRIBUTING.md` | 27 | `` A PR title without a recognised prefix is **silently dropped** from the changelog. So: prefix it. `` | A | "silently dropped from the changelog" becomes "listed under Other changes"; keep the instruction to prefix. |
| `templates/agents/convention-auditor.md` | 20 | `` - Layout (`docs/repo-layout.md`): bare `<repo>.git` beside `<repo>-main` and `<repo>-develop`; `core.bare` unset in the shared config; branch … `` | B | The expected develop first-parent shape becomes PR merge commits plus one back-merge PR merge per release. |
| `templates/agents/convention-auditor.md` | 23 | `` - Changelog and CI (`docs/ci.md`, `docs/commits-and-changelogs.md`): `cliff.toml` verbatim from the template where the profile has one; the workflows … `` | A | "`cliff.toml` verbatim from the template" becomes: no `cliff.toml` or `scripts/generate_changelog.py`; the release workflow's dev-tools checkout pinned to a tag; the PR-title workflow if adopted. |
| `templates/agents/convention-auditor.md` | 24 | `` - GitHub settings, via read-only `gh api`: default branch `develop` (or `staging` for websites); squash-only (`allow_squash_merge` true, merge-commit … `` | B | "squash-only (`allow_squash_merge` true, merge-commit and rebase off, `squash_merge_commit_title` = `PR_TITLE` …)" becomes merge-commit-only with `merge_commit_title` = `PR_TITLE`; the admin-bypass reason follows ci.md:26. |
| `templates/agents/release-preflight.md` | 20 | `` 1. Open pull requests into `develop`: `gh pr list --state open --base develop`. Any that should ship is a release blocker; list them. `` | B | An open PR from `back-merge-<tag>` is its own blocker (the previous release is unfinished), not a PR "that should ship". |
| `templates/agents/release-preflight.md` | 25 | `` 6. What would ship: `git log <last tag>..develop --first-parent --oneline`, listed and classified by Conventional Commit type. For a `VERSION.txt` … `` | B | Minor: the first-parent list now shows PR merge commits "<title> (#N)", back-merge PR merges and dev-build commits; classify the PR merges, skip release mechanics. |
| `templates/agents/release-preflight.md` | 26 | `` 7. The last tag, its date, and whether the release workflow of the previous release completed (including its `changelog` job where the profile has … `` | B | Add: the previous back-merge PR merged (`git merge-base --is-ancestor <last tag> origin/develop`). |
| `templates/agents/release-preflight.md` | 39 | `` 3. The exact command sequence from `docs/releases.md` for this repo's profile, as text for the user to authorise, starting from `<repo>-main`, … `` | B | "followed by the back-merge cascade" becomes "followed by `git back-merge` and the merge of its PR". |
| `templates/skills/dispatch/SKILL.md` | 40 | `` 7. After the user's merge, ask whether to cut a release, as the contract requires. Then close the branch lifecycle as `docs/branching.md` ("After the … `` | B | "confirm the merge from the pull request" becomes the ancestry test (`git merge-base --is-ancestor <branch> origin/develop`), as branching.md's new cleanup. |
| `templates/electron-builder.yml` | 18 | `` - '!{electron.vite.config.js,eslint.config.mjs,electron-builder.yml,cliff.toml,REUSE.toml,LICENSING.md,CHANGELOG.md,README.md,AGENTS.md,CLAUDE.md,.git … `` | A | Remove `cliff.toml` from the exclusion glob (keep it only while a repo still carries the file). |
| `templates/cliff.toml` | whole file |  | A | Delete. |
| `templates/generate_changelog.py` | whole file |  | A | Delete; HIGHLIGHTS_MODEL and MAX_LOG_CHARS move into the dev-tools script. |
| `templates/.github/workflows/release.yml` | 113-118 | `` # exist. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment: no git-cliff, no per-repo script; the shared dev-tools script at a pinned tag. |
| `templates/.github/workflows/release.yml` | 122-123 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read` to the job permissions (a job-level block sets unlisted scopes to none). |
| `templates/.github/workflows/release.yml` | 125-128 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff"); add a second `actions/checkout@v6` of `ParkviewLab/dev-tools` at a pinned `ref:` into `dev-tools/`, as pages-docs.yml:41-45. |
| `templates/.github/workflows/release.yml` | 133-136 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `templates/.github/workflows/release.yml` | 138-149 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Run the shared script (`uv run --no-project --with anthropic python dev-tools/scripts/<script> --mode=generate`), passing `GH_TOKEN` for the PR lookup. |
| `templates/.github/workflows/release.yml` | 159 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script (`--mode=insert`); the `docs(changelog): $TAG [skip ci]` commit stays. |
| `templates/.github/workflows/release-node.yml` | 152-156 | `` # (reads package.json as well as pyproject.toml). Needs cliff.toml + `` | A | Rewrite the job comment: no git-cliff, no per-repo script; the shared dev-tools script at a pinned tag. |
| `templates/.github/workflows/release-node.yml` | 160-161 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read` to the job permissions (a job-level block sets unlisted scopes to none). |
| `templates/.github/workflows/release-node.yml` | 163-165 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff"); add a second `actions/checkout@v6` of `ParkviewLab/dev-tools` at a pinned `ref:` into `dev-tools/`, as pages-docs.yml:41-45. |
| `templates/.github/workflows/release-node.yml` | 170-173 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `templates/.github/workflows/release-node.yml` | 175-181 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Run the shared script (`uv run --no-project --with anthropic python dev-tools/scripts/<script> --mode=generate`), passing `GH_TOKEN` for the PR lookup. |
| `templates/.github/workflows/release-node.yml` | 189 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script (`--mode=insert`); the `docs(changelog): $TAG [skip ci]` commit stays. |
| `templates/.github/workflows/release-electron.yml` | 109-112 | `` # built installers attached. Mirrors release-node.yml's changelog job (the `` | A | Rewrite the job comment: no git-cliff, no per-repo script; the shared dev-tools script at a pinned tag. |
| `templates/.github/workflows/release-electron.yml` | 116-117 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read` to the job permissions (a job-level block sets unlisted scopes to none). |
| `templates/.github/workflows/release-electron.yml` | 119-121 | `` fetch-depth: 0 `` | A | Keep `fetch-depth: 0` (drop "for git-cliff"); add a second `actions/checkout@v6` of `ParkviewLab/dev-tools` at a pinned `ref:` into `dev-tools/`, as pages-docs.yml:41-45. |
| `templates/.github/workflows/release-electron.yml` | 128-131 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `templates/.github/workflows/release-electron.yml` | 132-136 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Run the shared script (`uv run --no-project --with anthropic python dev-tools/scripts/<script> --mode=generate`), passing `GH_TOKEN` for the PR lookup. |
| `templates/.github/workflows/release-electron.yml` | 143 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script (`--mode=insert`); the `docs(changelog): $TAG [skip ci]` commit stays. |
| `templates/.github/workflows/release-txt.yml` | 7-9 | `` # `changelog` job: a docs repo has no Conventional-Commit signal to categorise, `` | A+B | Identical to the handbook's own release.yml: same two changes. |
| `templates/.github/workflows/release-txt.yml` | 81 | `` if ! gh release create "$TAG" --title "$TAG" --verify-tag --generate-notes; then `` | B | As release.yml:81. |
| `templates/.github/workflows/version-guard.yml` | 3-6 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment, as the handbook copy. |
| `templates/.github/workflows/version-guard.yml` | 16-44 | `` no-version-change: `` | B | Back-merge mode in the same job. Also fold in the two local variants, or a re-sync will drop them: paper-boxing's first-introduction rule and pensa-forma's Cargo.toml branch. |
| `templates/.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `templates/.github/workflows/dev-release-electron.yml` | 11 | `` # `git dev-release --open`). See the handbook's electron-tooling.md / releases.md. `` | B | Only if `git dev-release --open` is retired or redirected: "open a cycle with `git dev-release --open`" names the new route. |
| `templates/.github/workflows/dev-release-electron.yml` | 34 | `` *) echo "::error::package.json version '$V' has no -dev marker; the build would be indistinguishable from a release. Open a dev cycle first: git … `` | B | Same condition: the error text "Open a dev cycle first: git dev-release --open". |
| `templates/.github/release.yml` | new |  | B | Only if the exclusion route is chosen: the same label rule as .github/release.yml, for every VERSION.txt repo that runs release-txt.yml. Covered by REUSE.toml:15 (`templates/.github/**`). |
| `templates/.github/workflows/pr-title.yml` | new |  | A | Only if the title check is adopted: a new workflow template (name to choose) checking the PR title on `pull_request` to develop, exempting `back-merge-*` heads unless B gives that PR a Conventional title. Covered by REUSE.toml:15 (`templates/.github/**`). |

Deleted: `templates/cliff.toml`, `templates/generate_changelog.py`.

Changed: `README.md`, `REUSE.toml`, `AGENTS.md`, `CLAUDE.md`, `.github/workflows/version-guard.yml`, `.github/workflows/release.yml`, `docs/northstar.md`, `docs/northstar.html`, `docs/branching.md`, `docs/ci.md`, `docs/releases.md`, `docs/commits-and-changelogs.md`, `docs/ai-collaboration.md`, `docs/agents.md`, `docs/new-repo-checklist.md`, `docs/electron-tooling.md`, `docs/node-tooling.md`, `docs/docs-site.md`, `docs/in-flight_ideas.md`, `docs/handbook-improvements_ideas.md`, `templates/AGENTS.md.template`, `templates/CLAUDE.md.template`, `templates/CONTRIBUTING.md`, `templates/agents/convention-auditor.md`, `templates/agents/release-preflight.md`, `templates/skills/dispatch/SKILL.md`, `templates/electron-builder.yml`, `templates/.github/workflows/release.yml`, `templates/.github/workflows/release-node.yml`, `templates/.github/workflows/release-electron.yml`, `templates/.github/workflows/release-txt.yml`, `templates/.github/workflows/version-guard.yml`, `templates/.github/workflows/dev-release-electron.yml`.

New: .github/release.yml (B, only on the exclusion route); templates/.github/release.yml (B, same condition); templates/.github/workflows/pr-title.yml (A, only if the title check is adopted; the name is a placeholder).

REUSE and licence entries after the deletions: REUSE.toml:15 names both retired templates; remove the two entries. LICENSING.md and docs/licensing.md name neither file.

Reviewed, no change:

- branching.md:13, 55, 71 (the promotion stays a CLI `git merge --no-ff develop`; main still takes only release commits).
- ci.md:49 and new-repo-checklist.md:44 (main protection). With `back-merge-<tag>` as the head, main is never the head of a PR, so auto-deletion cannot reach it; the protection rule stands on its own.
- ci.md:138 and new-repo-checklist.md:45 (org ANTHROPIC_API_KEY), while the Highlights call stays in the shared script.
- releases.md:113 (why the back-merge exists) and repo-layout.md:44 (`git pull --ff-only` in the back-merge flow).
- docs-site.md:28: holds as long as the shared script keeps the `docs(changelog): <tag> [skip ci]` commit.
- parallel-work.md:46: defers to branching.md "After the merge"; changes with it, no edit of its own.
- website.md:12, 29, 51, 125: websites have no back-merge, guard or changelog job.
- The gate message "release tags must come from main — back-merge through, then re-tag from main" (templates release.yml:39, release-node.yml:42, release-electron.yml:38, release-txt.yml:44; .github/workflows/release.yml:44): about tags off main, unaffected.
- templates/.github/workflows/dev-release.yml:5, 38 and ci.md:121: the dev-build path stays.
- templates/skills/dispatch/SKILL.md:38 ("no merge into a trunk") and templates/agents/docs-currency-checker.md:20 (CHANGELOG.md as a record).
- handbook-improvements_ideas.md:52-59, 70, 204-205: the dated 2026-07 survey inventory, a record; may stay or be marked superseded.
- commits-and-changelogs.md:69: the pointer to releases.md and ci.md stays; the wiring it points at changes there.
- templates/.github/workflows/pages-docs.yml:41-45 (dev-tools checked out at `v1.1.0`): the pattern the changelog job copies; its own pin need not move with A.

## dev-tools

Read at 69d3e36 (main, v1.1.0).

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `scripts/<changelog script>` | new |  | A | The shared generator (the book names it `scripts/generate-changelog`): `--repo`, `--tag`, `--mode=generate` and `--mode=insert`, reads merged PRs via `gh`/API, pyproject/package.json/Cargo.toml metadata, the Highlights call. Covered by REUSE.toml:15 (`scripts/**`). |
| `tests/<changelog tests>` | new |  | A | Tests for every rule, including the measured cases. Covered by REUSE.toml:15 (`tests/**`). |
| `scripts/git-back-merge` | new |  | B | New helper: branch `back-merge-<tag>` from develop, merge main with a merge commit, add the open-cycle bump (code repos), push, open the PR; refuse on a stale develop; handle the strict up-to-date rule by merging develop into the branch, never into main. |
| `tests/<git-back-merge and git-dev-release tests>` | new |  | B | Tests for the helper and the fetch fix (a scratch repo; `gh` stubbed). |
| `scripts/git-dev-release` | 5-17 | `` #   git dev-release --open     # open the next cycle post-release: X.Y.(Z+1).dev0, no publish `` | B | Header: `--open` is retired, kept for VERSION.txt repos, or redirected to the back-merge branch (decision); the fetch requirement. |
| `scripts/git-dev-release` | 42-50 | `` branch="$(git rev-parse --abbrev-ref HEAD)" `` | B | After the branch and clean-tree checks, `git fetch origin develop` and refuse unless HEAD equals origin/develop (or `git pull --ff-only`). Without it, `--open` after the PR merges commits on a stale develop and the push is rejected. |
| `scripts/git-dev-release` | 54-56 | `` if [[ "$OPEN" == 1 ]]; then `` | B | The `--open` branch: follows the `--open` decision (the open-cycle bump moves into `git back-merge`). |
| `scripts/git-dev-release` | 80-86 | `` git push origin develop `` | B | The commit and `git push origin develop`: unchanged for dev builds (a direct push under the admin bypass), after the new fetch check. |
| `scripts/_sot.sh` | 6 | `` # Sourced (not run) by git-bump, git-release, git-dev-release. NOT executable, so `` | B | "Sourced (not run) by git-bump, git-release, git-dev-release": add git-back-merge if it sources the helpers for the open-cycle version. |
| `README.md` | 7 | `` Clone once, run `install.sh`. The installer symlinks every **executable** script in `scripts/` into `~/.local/bin/`, so each is on `$PATH` under its … `` | A+B | The install paragraph lists the commands (`git-<verb>` helpers, `build-pages-site`); add `git-back-merge` (B) and the changelog script (A). |
| `README.md` | 21 | `` - `python3` (3.13) for `build-pages-site`, which uses the standard library only. `` | A | Requirements: add what the changelog script needs (python3 or uv, `anthropic` for the Highlights call, `gh` or a token). |
| `README.md` | 23 | `` - `gh` (GitHub CLI) for `git dev-release`. `` | B | "`gh` (GitHub CLI) for `git dev-release`": also for `git back-merge`. |
| `README.md` | 73 | `` Run from `develop`. Bumps the source of truth to the next **dev** version, commits, pushes `develop`, and dispatches the repo's `dev-release.yml` … `` | B | `git dev-release` "commits, pushes develop": add the fetch and fast-forward check. |
| `README.md` | 78 | `` git dev-release --open      # open the next cycle post-release: X.Y.(Z+1).dev0 (no publish) `` | B | `git dev-release --open` usage line: follows the `--open` decision. |
| `README.md` | 83 | `` - **`--open`** is run right after a release (part of the back-merge cascade) to set `develop`'s honest version to the next-patch placeholder. `` | B | "`--open` is run right after a release (part of the back-merge cascade)": the open cycle moves into the back-merge PR. |
| `README.md` | 88 | `` ## `build-pages-site` — build a repo's documentation site `` | A+B | Add a section for the changelog script (A) and one for `git back-merge` (B), beside the `build-pages-site` section. |
| `README.md` | 161 | `` Releases are tag-driven and cut from `main`; CI gates publish on the tag being reachable from `origin/main`. The full flow + rationale (why bump+tag … `` | B | "the back-merge cascade" becomes the back-merge PR. |
| `README.md` | 168 | `` # then back-merge main -> develop `` | B | "# then back-merge main -> develop" becomes "# then git back-merge, and merge its PR". |
| `README.md` | 171 | `` dev-tools is itself a `VERSION.txt` repo and is **released with these very tools** — `VERSION.txt` is the source of truth, bumped by `git bump` and … `` | B | dev-tools' own release: its back-merge also becomes a PR (and the version guard's back-merge mode must accept its `-dev` VERSION.txt). |
| `.github/workflows/test.yml` | 3-4 | `` # The unit tests of scripts/build-pages-site: standard-library unittest on the `` | A+B | The comment names only build-pages-site's tests; name the new ones. Line 24 (`python3 -m unittest discover -s tests`) runs new Python unittest files as they are; a bash test harness or a third-party dependency would need a new step. |
| `.github/workflows/version-guard.yml` | 3-6 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment (byte-identical to the template). |
| `.github/workflows/version-guard.yml` | 16-44 | `` no-version-change: `` | B | Back-merge mode; must accept the `-dev` VERSION.txt that dev-tools' develop carries (1.1.1-dev). |
| `.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 18 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Pointer line "PRs are squash-merged": re-sync (the sync also replaces the older hard-wrapped block). |
| `CLAUDE.md` | 18 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | As AGENTS.md:18. |

Deleted: none.

Changed: `scripts/git-dev-release`, `scripts/_sot.sh`, `README.md`, `.github/workflows/test.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`.

New: scripts/<changelog script> and its tests (A); scripts/git-back-merge and tests for it and for the git-dev-release fix (B).

REUSE and licence entries after the deletions: None. REUSE.toml:15 covers `scripts/**` and `tests/**`, so the new files are covered; LICENSING.md:16 already lists both trees.

Reviewed, no change:

- scripts/git-bump, scripts/git-release, scripts/_sot.sh functions and scripts/build-pages-site: `git describe --tags` finds the newest tag under real merges as under squash (earlier audit, confirmed by reading the code).
- tests/test_build_pages_site.py (builds linear histories) and install.sh (symlinks every executable; README:15 already says a new command needs a re-run).
- REUSE.toml:15 and LICENSING.md:16.

## cobalt-grinding

Read at a25741c.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 99-104 | `` # exist. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 108-109 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 111-113 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 119-122 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 124-135 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 145 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 20-48 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 30 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 19-20 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 26-28 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 39 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 41-42 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 32-34 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 6-12 | `` prefix, produced by [git-cliff](https://git-cliff.org/) using `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 18-20 | `` released version, then older versions. generate_changelog.py inserts `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `README.md` | 60 | `` Tag-driven via [`.github/workflows/release.yml`](.github/workflows/release.yml). A push of a `v*` tag fires four jobs: a **gate** (tag matches … `` | A | The Releasing text names git-cliff; describe the shared script. |
| `README.md` | 72 | `` The changelog job categorizes commits using [Conventional Commits](https://www.conventionalcommits.org/) prefixes (see [`cliff.toml`](cliff.toml) for … `` | A | "(see [`cliff.toml`](cliff.toml))": the link goes dead when cliff.toml is deleted. |
| `README.md` | 82 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| not surfaced in CHANGELOG \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `README.md` | 84 | `` Squash-merge PRs use the PR title as the commit subject — so the **PR title** is what needs the prefix. Commits without a recognised prefix are … `` | A+B | B: "Squash-merge PRs use the PR title as the commit subject"; A: "silently dropped" becomes Other changes. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None. REUSE.toml is a `**` catch-all (AGPL); both deleted files also carry their own SPDX headers.

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- .github/workflows/dev-release.yml:9, 42 ("via `git dev-release`", "open the dev cycle first"): the dev-build path stays.

## cogrind-workshop

Read at 26d72e4.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 62-67 | `` # exists. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 71-72 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 74-76 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 82-85 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 87-98 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 108 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 20-48 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 30 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 19-20 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 26-28 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 39 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 41-42 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 33-35 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 6-12 | `` prefix, produced by [git-cliff](https://git-cliff.org/) using `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 18-20 | `` released version, then older versions. generate_changelog.py inserts `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `README.md` | 21 | `` The workflow runs three jobs: a **gate** (tag matches `pyproject.toml`; tag reachable from `origin/main`) gates the **pypi** publish (wheel + sdist … `` | A | The Releasing text names git-cliff; describe the shared script. |
| `README.md` | 25 | `` The changelog job categorizes commits using [Conventional Commits](https://www.conventionalcommits.org/) prefixes (see [`cliff.toml`](cliff.toml)): `` | A | "(see [`cliff.toml`](cliff.toml))": the link goes dead when cliff.toml is deleted. |
| `README.md` | 35 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| not surfaced in CHANGELOG \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `README.md` | 37 | `` Squash-merge PRs use the PR title as the commit subject — so the **PR title** is what needs the prefix. Commits without a recognised prefix are … `` | A+B | B: "Squash-merge PRs use the PR title as the commit subject"; A: "silently dropped" becomes Other changes. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None. REUSE.toml is a `**` catch-all (AGPL); both deleted files also carry their own SPDX headers.

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- .github/workflows/dev-release.yml:9, 40 ("via `git dev-release`", "open the dev cycle first"): the dev-build path stays.

## conception-space

Read at 4cc6bf0.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release-electron.yml` | 90-93 | `` # built installers attached. Mirrors release-node.yml's changelog job (the `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release-electron.yml` | 97-98 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release-electron.yml` | 100-102 | `` fetch-depth: 0 `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release-electron.yml` | 109-112 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release-electron.yml` | 113-117 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release-electron.yml` | 124 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 5 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 16-44 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 18-19 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 23 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 18-19 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 23 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 18-19 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 20 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 25-27 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 38 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 40-41 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 6-8 | `` # Python (changelog tooling: scripts/generate_changelog.py) `` | A | "# Python (changelog tooling: scripts/generate_changelog.py)" and its `__pycache__`/`*.py[cod]` lines: remove; no other Python remains in this repo. |
| `REUSE.toml` | 11 | `` # cliff.toml and scripts/generate_changelog.py are mirrored verbatim from the handbook.) `` | A | Comment "cliff.toml and scripts/generate_changelog.py are mirrored verbatim from the handbook" goes. |
| `REUSE.toml` | 18 | `` "cliff.toml", `` | A | Remove `"cliff.toml"` (follows the deletion). Keep `"scripts/**"`: prepare-legal.mjs and clean-oss-licenses.mjs remain. |
| `electron-builder.yml` | 16 | `` - '!{electron.vite.config.js,eslint.config.mjs,electron-builder.yml,cliff.toml,REUSE.toml,LICENSING.md,CHANGELOG.md,README.md,AGENTS.md,CLAUDE.md,.git … `` | A | Remove `cliff.toml` from the exclusion glob. |
| `.github/workflows/dev-release-electron.yml` | 11 | `` # `git dev-release --open`). See the handbook's electron-tooling.md / releases.md. `` | B | Only if `git dev-release --open` is retired or redirected (as the template). |
| `.github/workflows/dev-release-electron.yml` | 34 | `` *) echo "::error::package.json version '$V' has no -dev marker; the build would be indistinguishable from a release. Open a dev cycle first: git … `` | B | Same condition: the error text. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release-electron.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `REUSE.toml`, `electron-builder.yml`, `.github/workflows/dev-release-electron.yml`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: REUSE.toml:18 `"cliff.toml"` goes, and the comment at :11. `"scripts/**"` (:19) stays for the two .mjs scripts. LICENSING.md names neither file.

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- README.md describes no release flow.

## deco-assaying

Read at a91a25a.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 103-108 | `` # exist. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 112-113 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 115-117 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 123-126 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 128-139 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 149 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 20-48 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 30 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 19-20 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 26-28 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 39 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 41-42 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 14-16 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 12-18 | `` prefix, produced by [git-cliff](https://git-cliff.org/) using `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 24-26 | `` released version, then older versions. generate_changelog.py inserts `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `README.md` | 393 | `` The workflow runs four jobs: a **gate** (tag/SSOT + ancestor checks) gates the two publish jobs — **docker** (multi-arch GHCR push, `vX.Y.Z` / `vX.Y` … `` | A | The Releasing text names git-cliff; describe the shared script. |
| `README.md` | 401 | `` The changelog job categorizes commits using [Conventional Commits](https://www.conventionalcommits.org/) prefixes (see [`cliff.toml`](cliff.toml)): `` | A | "(see [`cliff.toml`](cliff.toml))": the link goes dead when cliff.toml is deleted. |
| `README.md` | 411 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| not surfaced in CHANGELOG \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `README.md` | 413 | `` Squash-merge PRs use the PR title as the commit subject — so the **PR title** is what needs the prefix. Commits without a recognised prefix are … `` | A+B | B: "Squash-merge PRs use the PR title as the commit subject"; A: "silently dropped" becomes Other changes. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None. Both files carry their own MIT OR Apache-2.0 SPDX header and REUSE.toml does not name them; deleting them needs no entry change.

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- .github/workflows/dev-release.yml:9, 42 ("via `git dev-release`", "open the dev cycle first"): the dev-build path stays.

## ebony-enriching

Read at 73c4065.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 103-108 | `` # exist. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 112-113 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 115-117 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 123-126 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 128-139 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 149 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 20-48 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 30 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 19-20 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 26-28 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 39 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 41-42 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 40-42 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 12-18 | `` prefix, produced by [git-cliff](https://git-cliff.org/) using `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 24-26 | `` released version, then older versions. generate_changelog.py inserts `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `README.md` | 313 | `` After the publish jobs, a **changelog** job generates the new `CHANGELOG.md` section — an LLM-written "Highlights" paragraph plus a … `` | A | The Releasing text names git-cliff; describe the shared script. |
| `README.md` | 313 | `` After the publish jobs, a **changelog** job generates the new `CHANGELOG.md` section — an LLM-written "Highlights" paragraph plus a … `` | A | Same line: "(see [`cliff.toml`](cliff.toml))" goes dead when cliff.toml is deleted. |
| `README.md` | 323 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| not surfaced in CHANGELOG \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `README.md` | 325 | `` Squash-merge PRs use the PR title as the commit subject — so the **PR title** is what needs the prefix. Commits without a recognised prefix are … `` | A+B | B: "Squash-merge PRs use the PR title as the commit subject"; A: "silently dropped" becomes Other changes. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None, as deco-assaying (per-file headers, not named in REUSE.toml).

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- .github/workflows/dev-release.yml:9, 42 ("via `git dev-release`", "open the dev cycle first"): the dev-build path stays.
- README.md:303-309: the promotion commands stay.

## flint-slating

Read at fab033e.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 103-108 | `` # exist. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 112-113 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 115-117 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 123-126 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 128-139 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 149 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 20-48 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 30 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 19-20 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 26-28 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 39 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 41-42 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 16-18 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 12-18 | `` prefix, produced by [git-cliff](https://git-cliff.org/) using `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 24-26 | `` released version, then older versions. generate_changelog.py inserts `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `README.md` | 176 | `` After the publish jobs, a **changelog** job generates the new `CHANGELOG.md` section — an LLM-written "Highlights" paragraph plus a … `` | A | The Releasing text names git-cliff; describe the shared script. |
| `README.md` | 176 | `` After the publish jobs, a **changelog** job generates the new `CHANGELOG.md` section — an LLM-written "Highlights" paragraph plus a … `` | A | Same line: "(see [`cliff.toml`](cliff.toml))" goes dead when cliff.toml is deleted. |
| `README.md` | 186 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| not surfaced in CHANGELOG \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `README.md` | 188 | `` Squash-merge PRs use the PR title as the commit subject — so the **PR title** is what needs the prefix. Commits without a recognised prefix are … `` | A+B | B: "Squash-merge PRs use the PR title as the commit subject"; A: "silently dropped" becomes Other changes. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None, as deco-assaying.

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- .github/workflows/dev-release.yml:9, 42 ("via `git dev-release`", "open the dev cycle first"): the dev-build path stays.

## jonobones

Read at ff27c39.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 112-116 | `` # "Highlights" + the git-cliff list), commit it back to main, and create the `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 121-122 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 124-126 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 131-134 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 136-140 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 148 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 5 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 16-44 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 13-14 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 18 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 13-14 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 18 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 18-19 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 20 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 25-27 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 38 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 40-41 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `CHANGELOG.md` | 11-15 | `` produced by [git-cliff](https://git-cliff.org/) using `cliff.toml`. `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 21-23 | `` version, then older versions. generate_changelog.py inserts new `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `REUSE.toml` | 20 | `` "tsconfig.json", "tsconfig.build.json", "cliff.toml", `` | A | Remove `"cliff.toml"` (follows the deletion). Keep `"scripts/**"`: build-scoped-alias.mjs remains. |
| `.github/workflows/release.yml` | 118 | `` needs: [image, npm] `` | A | Drift, not required by A: no `gate` in `needs:`; the rewritten job is the moment to add the template gate. |
| `.github/workflows/release.yml` | 124 | `` - uses: actions/checkout@v5 `` | A | Drift: `actions/checkout@v5`; use @v6 for both checkouts, including the new dev-tools one. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `CHANGELOG.md`, `REUSE.toml`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: REUSE.toml:20 `"cliff.toml"` goes. `"scripts/**"` (:17) and LICENSING.md:28 stay (build-scoped-alias.mjs remains).

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- README.md describes no release flow; nothing to change there.

## paper-boxing

Read at 0a98c44.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 110-115 | `` # Two-phase invocation of generate_changelog.py keeps the LLM call to a `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 119-120 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 122-124 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 130-133 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 135-146 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 156 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 26-67 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 36 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 15-16 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 20 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 15-16 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 20 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 16 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button can only squash; **merging is the maintainer's action.** `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and the changelog is generated from it (via … `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 31 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 33 | `` A PR title without a recognised prefix is **silently dropped** from the changelog. So: prefix it. `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 16-18 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 9 | `` All notable changes to this project are recorded here. Each release entry has two parts: a **Highlights** paragraph, generated at release time by an … `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 14 | `` Keep-a-Changelog ordering: [Unreleased] at the top, then newest released version, then older versions. generate_changelog.py inserts new "## [vX.Y.Z] … `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `.github/workflows/version-guard.yml` | 11-16 | `` # paper-boxing departs from the handbook template in one respect: when the base `` | B | The local departure (first-introduction rule, lines 39-56): keep it in the new mode, or move it into the template (the comment says it is proposed for the template). |
| `docs/decisions.md` | 61 | `` Decided: when the base branch has no version file at all, `.github/workflows/version-guard.yml` passes and says that the file is new. Reason: a … `` | B | The guard decision stays true if the departure is carried into the new guard; if the template absorbs it, record that here. |
| `README.md` | 136 | `` Once the workflow is green, the back-merge cascade brings `main`'s release and changelog commits down: `main` into `develop` with `--no-ff` (`git -C … `` | B | "the back-merge cascade … `main` into `develop` with `--no-ff` (`git -C ../paper-boxing-develop merge --no-ff main`) … and develop opens the next development cycle": rewrite as `git back-merge` and its PR. |
| `README.md` | 138 | `` The workflow runs a **gate** (tag equals the version, tag reachable from `main`, version greater than the previous tag), then a **docker** matrix … `` | A | "(an LLM-written Highlights paragraph plus git-cliff's categorized list)": describe the shared script. |
| `README.md` | 142 | `` PRs are squash-merged with the PR title as the commit subject, so the PR title carries the [Conventional … `` | A+B | B: "PRs are squash-merged with the PR title as the commit subject"; A: "that `cliff.toml` reads", the dropped types, "merge commits are dropped as well" all change (the link to cliff.toml goes dead). |
| `docs/CONTRIBUTING.md` | 89 | `` Then the back-merge cascade: once the workflow is green, `git pull --ff-only` on `main` to pick up the changelog commit, then `main` merged into … `` | B | "Then the back-merge cascade: … `main` merged into `develop` with `--no-ff` …": rewrite as `git back-merge` and its PR. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `docs/decisions.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None, as deco-assaying (per-file headers).

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- docs/decisions.md:33 (the changelog job needs only the gate and the images; stays true).
- .dockerignore:20 `release-body.md`: stays while the shared script writes that file.
- README.md:128-133 and docs/CONTRIBUTING.md:78-87: the promotion commands stay.

## pensa-forma

Read at 72b4405.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/version-guard.yml` | 5 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 16-51 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 13-14 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 18 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 13-14 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 18 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 17-18 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 19 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 24-26 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 37 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 39-40 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `REUSE.toml` | 32 | `` "cliff.toml", `` | A | Remove `"cliff.toml"` (follows the deletion). |
| `REUSE.toml` | 29 | `` "scripts/**", `` | A | `"scripts/**"` matches nothing once the generator is deleted (it is the only file in scripts/); remove, or keep for future scripts. |
| `LICENSING.md` | 39 | `` \| Code, build configuration, workflows, lockfile (`src/**`, `crates/**`, `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `.github/**`, … `` | A | The code row lists `scripts/**` and `cliff.toml`; remove `cliff.toml` (and `scripts/**` if REUSE.toml:29 goes). |
| `.github/workflows/version-guard.yml` | 43-49 | `` if [ -f Cargo.toml ]; then `` | B | The local Cargo.toml branch: the back-merge mode must read Cargo.toml too; keep this branch, or move it into the template so a re-sync does not drop it. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `REUSE.toml`, `LICENSING.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: REUSE.toml:32 `"cliff.toml"` goes; REUSE.toml:29 `"scripts/**"` then matches nothing (remove or keep for later scripts); LICENSING.md:39 names `scripts/**` and `cliff.toml` and follows.

Reviewed, no change:

- README.md:31-34: the release workflow that "lands with the first release" calls the shared script from the outset; nothing to edit now.
- docs/in-flight_ideas.md:23-30: `git back-merge`'s open-cycle bump through `_sot.sh` cannot run here until dev-tools gains a Cargo kind, the gap that already blocks `git bump`; no edit, but a precondition for B here.
- No release workflow, no dev-release workflow, no README or CHANGELOG text naming the generator.

## pensa-grex

Read at fec0f0f.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release-electron.yml` | 99-102 | `` # built installers attached. Mirrors release-node.yml's changelog job (the `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release-electron.yml` | 106-107 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release-electron.yml` | 109-111 | `` fetch-depth: 0 `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release-electron.yml` | 118-121 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release-electron.yml` | 122-126 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release-electron.yml` | 133 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 5 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 16-44 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 26 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 18-19 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 23 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 18-19 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 23 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 20-21 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 22 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 27-29 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 40 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 42-43 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 6-8 | `` # Python (changelog tooling: scripts/generate_changelog.py) `` | A | Reword the comment; keep the Python ignores, since scripts/build_pages_site.py remains. |
| `REUSE.toml` | 11 | `` # cliff.toml and scripts/generate_changelog.py are mirrored verbatim from the handbook.) `` | A | Comment naming the mirrored cliff.toml and generator goes. |
| `REUSE.toml` | 17 | `` "cliff.toml", `` | A | Remove `"cliff.toml"` (follows the deletion). Keep `"scripts/**"`: three other scripts remain. |
| `electron-builder.yml` | 20 | `` - '!{electron.vite.config.js,eslint.config.mjs,electron-builder.yml,cliff.toml,REUSE.toml,LICENSING.md,CHANGELOG.md,README.md,AGENTS.md,CLAUDE.md,.git … `` | A | Remove `cliff.toml` from the exclusion glob. |
| `.github/workflows/release-electron.yml` | 11-13 | `` # Needs a repo secret ANTHROPIC_API_KEY for the changelog job's Highlights `` | A | Stale: the repo inherits the org secret (no repo secret exists); delete when the job is rewritten. |
| `.github/workflows/dev-release-electron.yml` | 11 | `` # `git dev-release --open`). See the handbook's electron-tooling.md / releases.md. `` | B | Only if `git dev-release --open` is retired or redirected. |
| `.github/workflows/dev-release-electron.yml` | 34 | `` *) echo "::error::package.json version '$V' has no -dev marker; the build would be indistinguishable from a release. Open a dev cycle first: git … `` | B | Same condition: the error text. |
| `docs/rust_port_ideas.md` | 756 | `` on `rust`, squash-merged as elsewhere; in the contained worktree layout, add a `` | B | Idea document: "squash-merged as elsewhere" goes stale; update when B lands (optional, a proposal not a rule). |
| `docs/rust_port_ideas.md` | 747 | `` gate is never touched. `git dev-release --open` opens a dev cycle and `git dev-release` `` | B | Idea document: "`git dev-release --open` opens a dev cycle"; follows the `--open` decision (optional). |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release-electron.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `REUSE.toml`, `electron-builder.yml`, `.github/workflows/dev-release-electron.yml`, `docs/rust_port_ideas.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: REUSE.toml:17 `"cliff.toml"` goes, and the comment at :11. `"scripts/**"` (:18) stays for build_pages_site.py and the two .mjs scripts. LICENSING.md names neither file.

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- docs/in-flight_ideas.md:77-80 (resolved key entry) and .github/workflows/pages.yml:18 (the changelog commit still exists).

## smalt-mcp

Read at d3242f3.

| File | Line | Current text | Proposal | Change |
|---|---|---|---|---|
| `cliff.toml` | whole file |  | A | Delete. |
| `scripts/generate_changelog.py` | whole file |  | A | Delete. |
| `.github/workflows/release.yml` | 103-108 | `` # exist. Two-phase invocation of generate_changelog.py keeps the LLM call `` | A | Rewrite the job comment for the shared script (no git-cliff, no per-repo script). |
| `.github/workflows/release.yml` | 112-113 | `` contents: write   # scoped here — only this job commits CHANGELOG.md back to main `` | A | Add `pull-requests: read`. |
| `.github/workflows/release.yml` | 115-117 | `` fetch-depth: 0          # full history + all tags for git-cliff `` | A | Keep `fetch-depth: 0` (drop "for git-cliff" where present); add the dev-tools checkout at a pinned tag into `dev-tools/`. |
| `.github/workflows/release.yml` | 123-126 | `` - name: Install git-cliff `` | A | Delete the "Install git-cliff" step. |
| `.github/workflows/release.yml` | 128-139 | `` run: uv run --with anthropic python scripts/generate_changelog.py --mode=generate `` | A | Generate phase from the shared script with `--no-project`; pass `GH_TOKEN`. |
| `.github/workflows/release.yml` | 149 | `` uv run python scripts/generate_changelog.py --mode=insert `` | A | Insert phase from the shared script. |
| `.github/workflows/version-guard.yml` | 9 | `` # The release back-merge (main→develop) is a direct push, not a PR, so it is not `` | B | Header comment: the back-merge is a PR checked by the back-merge mode. |
| `.github/workflows/version-guard.yml` | 20-48 | `` no-version-change: `` | B | Back-merge mode inside the `no-version-change` job (the required context). |
| `.github/workflows/version-guard.yml` | 30 | `` git fetch --no-tags --depth=1 origin "$BASE" `` | B | Delete the depth-one fetch. |
| `AGENTS.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `AGENTS.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `CLAUDE.md` | 19-20 | `` - **Merging a PR into `develop` is the user's call.** A broad directive ("fix all that", "finish it") authorizes work on the branch, **not** the … `` | B | Changes only if the ruling on who merges the back-merge PR alters the managed block's authorisation lines; re-sync. |
| `CLAUDE.md` | 24 | `` - PRs are **squash-merged**, so the **PR title** carries the Conventional Commit prefix (`feat:`/`fix:`/`docs:`/…) the changelog is generated from. `` | B | Re-sync from the changed template ("PRs are squash-merged"). |
| `docs/CONTRIBUTING.md` | 19-20 | `` - Open a PR into **`develop`**. The repo is **squash-only**, so the merge button `` | B | "The repo is squash-only, so the merge button can only squash" becomes merge-commit-only. |
| `docs/CONTRIBUTING.md` | 21 | `` - Releases are cut from **`main`** via the CLI (`git merge --no-ff develop`, then `` | B | Optional: add that each release ends with the back-merge PR. |
| `docs/CONTRIBUTING.md` | 26-28 | `` Because PRs are squash-merged, **the PR title becomes the commit subject**, and `` | A+B | B: "Because PRs are squash-merged, the PR title becomes the commit subject"; A: "(via git-cliff + `cliff.toml`)" becomes the shared script reading merged PR titles. |
| `docs/CONTRIBUTING.md` | 39 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| stays in git history, not surfaced \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `docs/CONTRIBUTING.md` | 41-42 | `` A PR title without a recognised prefix is **silently dropped** from the `` | A | "silently dropped" becomes "listed under Other changes". |
| `.gitignore` | 37-39 | `` # Transient release artifact: scripts/generate_changelog.py writes this for `` | A | The comment names scripts/generate_changelog.py; name the shared script, or drop the entry if it no longer writes release-body.md in the workspace. |
| `CHANGELOG.md` | 12-18 | `` prefix, produced by [git-cliff](https://git-cliff.org/) using `` | A | Preamble: "see `scripts/generate_changelog.py`" and "a list of merged commits … produced by git-cliff using `cliff.toml`" describe the retired generator; describe merged PRs and direct commits from the shared script. |
| `CHANGELOG.md` | 24-26 | `` released version, then older versions. generate_changelog.py inserts `` | A | Comment: "generate_changelog.py inserts new … sections directly below [Unreleased]": name the shared script (the marker rule stays). |
| `README.md` | 165 | `` After the publish jobs, a **changelog** job generates the new `CHANGELOG.md` section — an LLM-written "Highlights" paragraph plus a … `` | A | The Releasing text names git-cliff; describe the shared script. |
| `README.md` | 165 | `` After the publish jobs, a **changelog** job generates the new `CHANGELOG.md` section — an LLM-written "Highlights" paragraph plus a … `` | A | Same line: "(see [`cliff.toml`](cliff.toml))" goes dead when cliff.toml is deleted. |
| `README.md` | 175 | `` \| `chore:` / `ci:` / `build:` / `style:` \| _(dropped)_ \| not surfaced in CHANGELOG \| `` | A | "_(dropped)_" becomes "Maintenance". |
| `README.md` | 177 | `` Squash-merge PRs use the PR title as the commit subject — so the **PR title** is what needs the prefix. Commits without a recognised prefix are … `` | A+B | B: "Squash-merge PRs use the PR title as the commit subject"; A: "silently dropped" becomes Other changes. |

Deleted: `cliff.toml`, `scripts/generate_changelog.py`.

Changed: `.github/workflows/release.yml`, `.github/workflows/version-guard.yml`, `AGENTS.md`, `CLAUDE.md`, `docs/CONTRIBUTING.md`, `.gitignore`, `CHANGELOG.md`, `README.md`.

New: if A adopts the title check, a copy of the new title workflow (and its required context on develop).

REUSE and licence entries after the deletions: None, as deco-assaying (per-file headers).

Reviewed, no change:

- The release gate's message "release tags must come from main — back-merge through, then re-tag from main" (about tags off main) and the `docs(changelog): $TAG [skip ci]` commit line, which the shared script keeps.
- .github/workflows/dev-release.yml:9, 42 ("via `git dev-release`", "open the dev cycle first"): the dev-build path stays.
- src/smalt_mcp/storage/indexer.py:423 ("important for back-merge cascade hygiene"): about deterministic output, not the mechanism.

## GitHub settings (not files)

Read with `gh api` on 2026-09-17; unchanged from the earlier audit. All thirteen: `allow_squash_merge` true, `allow_merge_commit` false, `allow_rebase_merge` false, `merge_commit_title` MERGE_MESSAGE, `merge_commit_message` PR_TITLE, `squash_merge_commit_title` PR_TITLE, `delete_branch_on_merge` true, default branch develop, no rulesets, `enforce_admins` false, no linear-history requirement.

| Repository | develop: strict, required contexts | main protected | B needs | A needs (only if the title check is adopted) |
|---|---|---|---|---|
| handbook | true; reuse, no-version-change | yes | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| dev-tools | true; reuse, no-version-change | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| cobalt-grinding | true; reuse, no-version-change, test | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| cogrind-workshop | true; reuse, no-version-change, test | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| conception-space | true; reuse, no-version-change, checks | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| deco-assaying | true; reuse, no-version-change, test, licenses | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| ebony-enriching | true; reuse, no-version-change, test, licenses | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| flint-slating | true; reuse, no-version-change, test, licenses | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| jonobones | true; reuse, no-version-change, checks (24.x), checks (26.x), interop, docker, e2e | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| paper-boxing | true; test, integration, licenses, reuse, no-version-change | yes | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| pensa-forma | false; reuse, no-version-change | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| pensa-grex | false; reuse, checks, no-version-change | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |
| smalt-mcp | true; reuse, no-version-change, test, licenses | no | `allow_merge_commit` true, `merge_commit_title` PR_TITLE, `merge_commit_message` PR_BODY or BLANK; `allow_squash_merge` false if squash is replaced (decision 1) | add the title check's context to develop's required checks |

With `strict` true (eleven repositories), a `back-merge-<tag>` branch goes out of date if a feature merges while its checks run; `git back-merge` must then merge develop into the branch (never into main). pensa-forma and pensa-grex do not require up-to-date branches.

## Interactions between A and B, and decisions the rows depend on

- Order within each repository: A's workflow must be live before the first release that contains a real merge. Under B, git-cliff over `prev..tag` would list every conventionally prefixed branch commit beside the merge, and `commit_log` would feed all of them to the Highlights call.
- A's script must leave out the back-merge PR (head `back-merge-*`) and the open-cycle bump it carries; before B lands there is no such PR, so the rule is inert but harmless.
- Title check (A) against the back-merge PR title (B): "Back-merge: main → develop after <tag>" is not a Conventional Commit title. Either the check exempts `back-merge-*` heads or B titles the PR with a type (for example `chore:`).
- VERSION.txt repositories (handbook, dev-tools): B puts the back-merge PR into GitHub's generated notes; A decides whether they adopt the shared script. The rows at handbook release.yml:7-9 and :81, ci.md:117, releases.md:78 and :107, and commits-and-changelogs.md:8 follow that decision.
- The guard's back-merge mode (B) must admit the open-cycle bump in code repositories (the merged version is the next-patch dev version of the tag, not the tag), read Cargo.toml (pensa-forma), accept the `-dev` VERSION.txt marker (dev-tools develop holds 1.1.1-dev), and keep paper-boxing's first-introduction rule. The template must absorb the two local variants, or a re-sync from it removes them.
- Fate of `git dev-release --open` (B): retired, kept for VERSION.txt repositories, or redirected to the back-merge branch. Rows in dev-tools (git-dev-release, README:78, :83), the electron dev-release templates and copies, electron-tooling.md:72 and pensa-grex docs/rust_port_ideas.md:747 depend on it.
- Who merges the back-merge PR (B): the rows at ai-collaboration.md:25-28, branching.md:70, the pointer templates' lines 9-10 (and their copies in every repository) and northstar axiom 4 depend on the ruling.
- pensa-forma: B's open-cycle bump through `_sot.sh` cannot run until dev-tools gains a Cargo kind (pensa-forma docs/in-flight_ideas.md:23-30); A's script must read Cargo.toml for the project name.
- Branch name: book 131's design page says `back-merge/<tag>`; this revision uses `back-merge-<tag>`, which the prefix rule at branching.md:21 ("hyphen not slash") requires (review F45). The rows assume the hyphen form.
- Pointer re-sync: after the template changes, `scripts/sync-agent-files.sh` must run for every repository; it also reaches repositories outside this inventory (parkviewlab.ai and zoestum.ai carry "squash-merged" in AGENTS.md, per review F21, not re-checked here).

## Corrections to the earlier audit and review

- Every handbook line number cited by the earlier audit (taken on handbook-develop 502dadc) still holds on handbook-main v0.23.1 for the lines rechecked: README 21, 44, 67; branching.md 36, 54, 62-63, 68, 70, 75, 94-105; ci.md 12, 16, 26, 28-48, 71-73, 110, 117, 129; releases.md 71, 89, 101, 107, 111-132, 146, 152; commits-and-changelogs.md 8, 21, 25, 27-33, 53, 56-69; ai-collaboration.md 25-28, 32; new-repo-checklist.md 19, 40-43, 71; northstar.md 24 and northstar.html 213-215; the three version-guard copies are still byte-identical.
- evidence.json auditText.findings[1] (dev-tools main must be protected before a PR-based back-merge, a blocker) does not apply to B as now specified: the head is `back-merge-<tag>`, never main. That main is unprotected in eleven of thirteen repositories remains a separate divergence from ci.md:49.
- auditText.findings[2] selected the mode by `head.ref == 'main'` and required the merged version to equal main's; under B the selector is a `back-merge-*` head from this repository, and the merged version is the open-cycle version in code repositories.
- auditText.findings[21]'s cascade (`gh pr create --base develop --head main`) is superseded by `git back-merge` and its branch.
- auditText.findings[45] still holds: ci.md:117 says dev-tools runs release-txt.yml, but dev-tools has no release workflow; its latest GitHub Release is v1.0.1 although the tag v1.1.0 exists.
- Review F21: `git grep -l -i squash` in handbook-main finds 16 files, as the review said. Seven repository READMEs contain squash wording (cobalt-grinding, cogrind-workshop, deco-assaying, ebony-enriching, flint-slating, paper-boxing, smalt-mcp), and every docs/CONTRIBUTING.md does.
- Review F40: the book's "eleven copies" of the generator is right; with the eleven `cliff.toml` copies and the two templates, A deletes 24 files.
- Two local guard variants were not in the earlier audit: paper-boxing's first-introduction rule (version-guard.yml:11-16, 39-56; docs/decisions.md:61) and pensa-forma's Cargo.toml branch (version-guard.yml:43-49).

