# Facts for the revised proposal "Real merges and the back-merge pull request"

Established on 2026-09-17 (UTC 2026-09-18) from the released handbook (`handbook-main` at `4b572e0`, v0.23.1, equal to `origin/main`), dev-tools (`dev-tools-main` at `69d3e36`, v1.1.0, equal to `origin/main`), fresh bare clones of the thirteen repositories that run the version guard, GitHub's REST API (read-only calls: repository settings, branch protection, rulesets, check runs, workflow runs, and the repository activity endpoint, which records every push, pull-request merge, force push and ref deletion with its before and after SHAs), GitHub's documentation, and local simulations. Nothing on GitHub and no existing worktree was changed.

Line references are to the files as released: `docs/…` and `templates/…` are the handbook's, `scripts/…` and `README.md` are dev-tools'. Short SHAs are from the repositories named.

Artefacts, all under `/private/tmp/claude-501/-Users-gary-dev/e994abf8-7c35-4038-ac9d-b7e6b855627e/scratchpad/revise/`:

- `sim/backmerge-check.sh`: the check (item 6).
- `sim/run-sim.sh` and `sim/sim-output.txt`: the main simulation, 24 cases, all as expected (bash 3.2, git 2.54).
- `sim/replay-bash5.sh` and `sim/replay-bash5-output.txt`: 21 of those cases replayed under bash 5.2.37 and git 2.49.1 (Alpine container), all as expected.
- `sim/run-sim-kinds.sh` and `sim/sim-kinds-output.txt`: the check on `package.json` and `VERSION.txt` repositories, 6 cases, all as expected.
- `sim/shallow-repro.sh` and `sim/shallow-output.txt`: the depth-one fetch reproduction (item 7).
- `clones/`, `prs/`, `activity.json`, `attribution.json`, `releases.json`, `history.json`, `settings.tsv`, `protection.txt`: the collected data; `activity.py`, `attribute.py`, `analyse.py`, `releases.py`, `mergecount.sh`: the scripts that produced it.

## 1. Writes to `develop` and `main` that do not pass through a pull request

No required check runs before any of these writes lands. `main` has no required checks anywhere (item 3). `develop` requires checks in all thirteen repositories, but with `enforce_admins` false, and every push below was made by `garycoding`, an organisation admin (`gh api orgs/ParkviewLab/memberships/garycoding`: role admin), so each direct push to `develop` lands by the administrator bypass that `docs/ci.md:26` prescribes ("let admins bypass"). What runs afterwards is only what the push triggers, and it runs on the head of the push, not on each commit the push carries.

| Write | Command | Where | Commit made | Workflows that run after it lands |
|---|---|---|---|---|
| Promotion | `git merge --no-ff develop` in `<repo>-main` | `docs/releases.md:65` (no script; no `-m`, so the message is the operator's; observed "Release: develop → main for vX.Y.Z", "Promote develop for v3.5.1") | a merge commit on `main` | none on the merge commit itself: it is not the head of the push. Verified: paper-boxing `c60b282` (promotion for v0.1.1) has zero check runs. |
| Release bump and tag | `git bump <kind>`, `git release`, `git push --follow-tags` | `scripts/git-bump:52-53` (`git add $(sot_write "$new")`, `git commit -m "release v$new"`); `scripts/git-release:43` (`git tag -a`); push at `docs/releases.md:68` | "release vX.Y.Z" on `main`, plus an annotated tag | on the bump commit, push to `main`: test*, reuse, license-check where present, and the docs-site workflow where present (paper-boxing `18db127`: Test, REUSE, License check, Deploy the site). On the tag: the release workflow (gate, publish, changelog). The gate runs after `main` has moved; it guards publishing, not landing. |
| Changelog commit | the release workflow's `changelog` job | `templates/.github/workflows/release.yml:161-175` (commit at 174, `git push origin HEAD:main` at 175); `release-node.yml:201-202`; `release-electron.yml:151-152`; absent from `release-txt.yml` | "docs(changelog): vX.Y.Z [skip ci]" by github-actions[bot] on `main` | none: `[skip ci]` suppresses push workflows, and events made with `GITHUB_TOKEN` create no workflow runs. Verified: paper-boxing `4d078ff` has zero check runs. |
| Back-merge | `git -C ../<repo>-develop merge --no-ff main -m "Back-merge: main → develop after <tag>" && git -C ../<repo>-develop push` | `docs/releases.md:125-126` (no script) | a merge commit on `develop` (historically, most were fast-forwards: item 3) | push to `develop`: test*, reuse, license-check (paper-boxing `a3fc2cf`: integration, licenses, test, reuse). The version guard never runs: it triggers on `pull_request` only. When the back-merge was a fast-forward whose head is the `[skip ci]` changelog commit, nothing ran at all: cobalt-grinding `983ee36`, cogrind-workshop `25098a3`, jonobones `51531e6`, smalt-mcp `1bbe671` and `3dee2ea` have no workflow runs. |
| Open-cycle bump (code repositories) | `git dev-release --open` in `<repo>-develop` | `scripts/git-dev-release:54-56` (`new=$(sot_dev_version "$cur" patch)`, message "chore: open $new dev cycle"), `81-83` (`git add`, `git commit`, `git push origin develop`); required by `docs/releases.md:146` | "chore: open X.Y.(Z+1).dev0 dev cycle" on `develop` | push to `develop`: test*, reuse, license-check (paper-boxing `953e125`; smalt-mcp `84e9832`). Version guard: never. |
| On-demand dev build | `git dev-release <patch\|minor\|major>` | `scripts/git-dev-release:64-65` (message "chore: dev build v$new"), `81-83` (commit and `git push origin develop`), `90` (`gh workflow run dev-release.yml --ref develop`) | "chore: dev build vX.Y.Z.devN" on `develop` | push to `develop`: test*, reuse, license-check; then `dev-release.yml` by `workflow_dispatch` on `develop` (smalt-mcp `cf7491a`: License check, REUSE, Test on push; Dev release on dispatch; the same for cobalt-grinding `a25741c` and flint-slating `5aa3487`). |

Related writes, recorded for completeness:

- `docs/releases.md:127` merges `develop` into each open working branch; that writes working branches, not the trunks.
- Tags are unprotected (no rulesets anywhere). The activity endpoint records six deletions of release tags, most followed by re-creation at another commit: handbook v0.7.0 (2026-06-15), flint-slating v0.1.3 (2026-05-18, never re-created), smalt-mcp v1.2.0 (2026-05-18), conception-space v0.8.5 (2026-07-20), pensa-grex v1.0.0 (2026-07-20) and pensa-grex v3.5.1 (2026-09-16). The last is the recent case: the release workflow for v3.5.1 on `0b34ac1` failed (run 35054660412), a fix was merged (#104), `develop` was promoted a second time, the tag was deleted at 04:26:16Z and re-created on `6faff3d`.
- Two force pushes to `main` are recorded, both on 2026-07-20: conception-space (`2fa4624` to `4c3e675`) and pensa-grex (`c824e00` to `f4a3efa`).

Per release, a code repository therefore writes `main` twice (the promotion and bump in one push, then the bot's changelog commit) and `develop` once or twice by direct push (the back-merge, then the open cycle, sometimes in one push), plus one direct push per on-demand dev build. A `VERSION.txt` repository writes `main` once and `develop` once.

Two discrepancies in the current documents surfaced while establishing this:

- `docs/releases.md:152` says `VERSION.txt` repositories skip the open cycle; dev-tools, a `VERSION.txt` repository, has opened four ("chore: open 1.1.1-dev dev cycle", `6a4c35d`, and three earlier), following its own README (`README.md:83`).
- `docs/ci.md:117` names dev-tools among the repositories that run `release-txt.yml`; dev-tools has no release workflow (`.github/workflows` holds `reuse.yml`, `test.yml`, `version-guard.yml`), so its tags are checked by no gate. `README.md:171` agrees with the repository ("no CI publish step").
- `scripts/git-dev-release:90` dispatches `dev-release.yml` by file name; the two Electron repositories (conception-space, pensa-grex) name theirs `dev-release-electron.yml` (workflow name "Dev release"), so by reading the code the script's dispatch would fail there (not observed; the script's own message for that case is "couldn't dispatch dev-release.yml"). conception-space's four Electron dev builds (2026-06-15 to 2026-07-20) were dispatched without any dev-build commit.

## 2. The dev build: committed version or workspace version

What the dev-publish workflows read. `dev-release.yml` (template and all six copies, identical but for licence headers and cogrind-workshop's missing docker job) checks out `develop` and reads the version only from the working tree: the gate reads `pyproject.toml` with `tomllib` and refuses a version without `.dev`/`-dev` ("open the dev cycle first", `templates/.github/workflows/dev-release.yml:35-39`); the docker job builds from the checkout as context, and every Python Dockerfile copies `pyproject.toml` and `uv.lock` from that context (deco-assaying, ebony-enriching, flint-slating, smalt-mcp, cobalt-grinding; paper-boxing uses `uv sync --locked`); the TestPyPI job runs `uv build` on the checkout. `dev-release-electron.yml:29-35` checks `package.json` for a `-dev` marker and electron-builder names the installers from it. Nothing in either workflow requires the version to be a commit.

Feasibility, tested. In a scratch project, `uv version 0.1.2.dev17` rewrote both `pyproject.toml` and `uv.lock`, `uv sync --locked` then succeeded, `importlib.metadata` reported 0.1.2.dev17, and `uv build` produced `vtest-0.1.2.dev17` (uv 0.11.16). `npm version 3.5.2-dev17 --no-git-tag-version` rewrote `package.json` and `package-lock.json`, and `npm ci --dry-run` succeeded. A workflow step that sets the version in the workspace before the build, in each job that builds, is therefore sufficient for the published artefacts. Two constraints apply. PyPI and TestPyPI never accept a file name twice (https://pypi.org/help/#file-name-reuse), so each build needs a distinct N; `github.run_number` is unique per workflow and increases, but "does not change if you re-run the workflow run" (https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#github-context), so a re-run after a successful upload would collide unless the upload skips existing files or N includes `github.run_attempt`. The target X.Y.Z would come from the newest `v*` tag and a `kind` input, which is `_sot.sh`'s arithmetic from a plain version (`scripts/_sot.sh:62-81`).

What reads the committed version on `develop`:

1. The two dev-publish gates and builds above.
2. `version-guard.yml`, which compares head against base and is indifferent to the value.
3. `git dev-release` itself, which derives the next dev version and its counter from it (`scripts/_sot.sh:93-110`).
4. `git bump` at the next release, after the promotion has carried `develop`'s version to `main`: from a dev version `patch|minor|major` re-point off the last tag and `release` finalises the declared target (`scripts/_sot.sh:62-81`); from a plain version the kinds increment in place and `git bump release` refuses ("version did not change", `scripts/git-bump:46-49`).
5. Anything built from `develop` outside the dev-publish workflow: `/admin/version` in the Python servers (deco-assaying `routes.py:763`, ebony-enriching `server.py:185`, flint-slating `routes.py:83`, smalt-mcp `server.py:211`, paper-boxing's backend, frontend and MCP server), an editable install, a locally built image, and pensa-grex's update check, which compares the running version with the newest release tag (`src/main/update.js:27-51`; its test treats 3.3.1-dev0 after 3.3.0 as current).

If dev versions were no longer committed at all, `develop` would carry the last released version between releases. The open-cycle commit and its direct push would disappear, as would the on-demand dev-build push; but item 5 would report the last release for unreleased code, which is what `docs/releases.md:136` and `:146` exist to prevent ("develop now reports e.g. 0.3.1.dev0 everywhere"); `git bump release` would lose its meaning; a minor or major re-point would no longer persist between builds; the two dev-publish gates would change from "the file carries a dev marker" to "compute the version"; and the record of which commit a dev build came from would move from the "chore: dev build" commit to the workflow run and the image's `sha-` tag. A middle course is also feasible: keep the open-cycle placeholder committed once per release (it can travel inside the back-merge pull request, item 6), and set only the per-build `.devN` in the workspace. That removes the dev-build pushes (five in all thirteen histories: cobalt-grinding, deco-assaying, ebony-enriching, flint-slating and smalt-mcp, one each) while `develop` still reports X.Y.(Z+1).dev0. A minor or major re-point would then be a per-build input, and the published dev version could name a different target from the one `develop` reports.

## 3. The thirteen repositories

Settings, identical in all thirteen unless stated: default branch `develop`; squash merging only (`allow_merge_commit` and `allow_rebase_merge` false); `allow_auto_merge` false; `allow_update_branch` false; `delete_branch_on_merge` true; `squash_merge_commit_title` PR_TITLE; `squash_merge_commit_message` COMMIT_MESSAGES, except ebony-enriching, PR_BODY; `merge_commit_title` MERGE_MESSAGE and `merge_commit_message` PR_TITLE (GitHub's defaults, inert while merge commits are disabled); no repository rulesets, and `gh api orgs/ParkviewLab/rulesets` returns none.

Protection of `develop`: in all thirteen, force pushes and deletions blocked, `enforce_admins` false, no required reviews, no linear-history requirement, no push restrictions. `strict` (require up to date) is true in eleven and false in pensa-grex and pensa-forma. Required contexts: handbook, dev-tools and pensa-forma `reuse`, `no-version-change`; cobalt-grinding and cogrind-workshop add `test`; conception-space adds `checks`; pensa-grex `reuse`, `checks`, `no-version-change`; deco-assaying, ebony-enriching, flint-slating and smalt-mcp add `test`, `licenses`; paper-boxing `test`, `integration`, `licenses`, `reuse`, `no-version-change`; jonobones `reuse`, `no-version-change`, `checks (24.x)`, `checks (26.x)`, `interop`, `docker`, `e2e`.

Protection of `main`: only the handbook and paper-boxing protect it (no required checks, force pushes and deletions blocked, `enforce_admins` false), as `docs/ci.md:49-63` prescribes for all; the other eleven return "Branch not protected".

Back-merges and open-cycle commits in the last three releases, from the activity endpoint (event type `push` means a direct push; `pr_merge` means a pull request). "ff" means `develop` was moved onto `main`'s commits with no merge commit; "merge" means a `--no-ff` merge commit.

| Repository | Releases | Back-merges (all direct push) | Open-cycle commits (all direct push) | Direct pushes to `develop` for these |
|---|---|---|---|---|
| handbook (`VERSION.txt`) | v0.22.0, v0.23.0, v0.23.1 | 3 merge | 0 (skips the open cycle) | 3 |
| dev-tools (`VERSION.txt`) | v1.0.0, v1.0.1, v1.1.0 | 2 ff, 1 merge | 3 | 4 |
| cobalt-grinding | v0.1.0 (only release) | 1 ff | 1 | 2, plus 1 dev build |
| cogrind-workshop | v0.1.0 (only release) | 1 ff | 1 | 2 |
| conception-space | v0.8.4, v0.8.5, v0.8.6 | 3 ff | 3 (each in the same push as the back-merge) | 3 |
| deco-assaying | v0.3.3, v0.3.4, v0.3.5 | 3 ff | 3 (same push) | 3 |
| ebony-enriching | v0.1.8, v0.1.9, v0.1.10 | 3 ff | 3 (same push) | 3 |
| flint-slating | v0.1.4, v0.1.5, v0.1.6 | 1 merge, 2 ff | 3 | 4, plus 1 dev build |
| jonobones | v0.1.3, v0.1.4, v0.1.5 | 3 ff (v0.1.3 and v0.1.4 predate the handbook flow: version branches merged locally into `develop`) | 0 | 3 |
| paper-boxing | v0.1.0, v0.1.1 | 2 merge | 2 | 4 |
| pensa-forma | none released | 0 | 0 | 0 |
| pensa-grex | v3.4.0, v3.5.0, v3.5.1 | 2 ff, 1 merge | 3 | 4 |
| smalt-mcp | v1.3.1, v1.3.2, v1.3.3 | 3 ff | 2 | 4, plus 1 dev build |
| Total | 31 releases | 31 (8 merge, 23 ff), none by pull request | 24, none by pull request | 39, plus 3 dev builds |

The only back-merges ever made by pull request are smalt-mcp #36 (2026-05-18) and #40 (2026-06-15), both headed by `main` and merged with a merge commit while merge commits were still enabled; both predate smalt-mcp's adoption of the version guard (#42). Promotions by pull request exist only in early history (deco-assaying #2, #4, #6, #9; smalt-mcp #5 to #39; ebony-enriching #7 to #16; dev-tools #2), and one working branch was merged straight into `main` by pull request (cogrind-workshop #1, "ci: bump action pins to Node 24", 2026-06-25).

Hand-resolved merges. Every two-parent merge reachable from any branch or tag in the thirteen clones (217) was compared with `git merge-tree --write-tree` of its parents. None conflicts and none differs from the automatic merge. Of the 217, 31 are back-merge merge commits (second parent a commit on `main`'s first-parent line, the merge itself not on it): handbook 16, pensa-grex 6, smalt-mcp 3, paper-boxing 2, and one each in dev-tools, conception-space, deco-assaying and flint-slating. So no back-merge in the recorded history needed a hand resolution, and none changed anything beyond the automatic merge. (The many fast-forward back-merges create no merge commit and cannot conflict.)

## 4. GitHub capabilities

- Merge methods by target branch. A ruleset's "Require a pull request before merging" rule can restrict the allowed merge methods (`allowed_merge_methods`: merge, squash, rebase; at least one) for the branches the ruleset targets. Documentation: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets and https://docs.github.com/en/rest/repos/rules. A ruleset targets refs by name pattern (`conditions.ref_name` include and exclude, https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository); no condition refers to a pull request's head branch, so the allowed methods cannot differ by head branch. Rulesets layer with classic protection, the most restrictive rule applying (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets). Consequence: with merge commits allowed for `develop` at all, they are allowed for every pull request into it; with squash allowed beside them, the back-merge pull request can be squashed by the button.
- Tag protection. A ruleset whose target is tags can apply "Restrict updates" (`update`), "Restrict deletions" (`deletion`) and "Block force pushes" (`non_fast_forward`) to tags matching `v*`; the first two are documented as allowing only users with bypass permission (same pages). With an empty `bypass_actors` list no actor holds bypass permission, so by the documented rule nobody, administrators included, could move or delete a matching tag. That last step is an inference from the documentation's wording, not tested (no setting may be changed here). It would have refused all six recorded tag deletions (item 1), including pensa-grex's v3.5.1 recovery, which would then have had to ship as v3.5.2.
- What a `pull_request` job checks out. `GITHUB_REF` is `refs/pull/<n>/merge` and `GITHUB_SHA` its "last merge commit" (https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request); `actions/checkout` checks out that synthetic merge. Verified in handbook run 35293024067: `HEAD is now at b6eb17e Merge eaced26… into c0e5523…`; `gh api repos/ParkviewLab/handbook/git/commits/b6eb17e…` gives parents `c0e5523` (the base tip) and `eaced26` (the head). `github.event.pull_request.head.sha` is the head branch's commit (same page). `github.event.pull_request.base.sha` is a payload field whose refresh rule GitHub does not document; community reports state it is the base tip when the pull request was opened or last force-pushed, not a value that follows the base (https://github.com/orgs/community/discussions/59677). The reliable base for a check is therefore the synthetic merge's first parent, `git rev-parse HEAD^1`. Pull request workflows do not run at all while the pull request has a merge conflict (same page). Check runs of `pull_request` workflows are recorded against the head SHA: paper-boxing PR #10's head `fab1d26` carries test, integration, licenses, reuse and no-version-change.
- Skipped required checks. A job skipped by an `if:` condition reports success; a workflow skipped by path or branch filtering or by a commit message leaves its checks pending, which blocks merging (https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks). For a pull request the commit message examined is the head commit's (https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs). Events made with `GITHUB_TOKEN` create no new workflow runs, except `workflow_dispatch` and `repository_dispatch` (https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
- Merge commit title and message. `merge_commit_title`: PR_TITLE or MERGE_MESSAGE ("Merge pull request #123 from branch-name"); `merge_commit_message`: PR_BODY, PR_TITLE or BLANK (https://docs.github.com/en/rest/repos/repos#update-a-repository; https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-merging-for-pull-requests). All thirteen hold the defaults, MERGE_MESSAGE and PR_TITLE. `gh pr merge --merge --subject <text> --body <text>` overrides both for one merge, and `--match-head-commit <sha>` refuses the merge unless the head is that commit (gh 2.92.0).
- Two further facts bear on the design. A pull request is marked merged when its head commits become reachable from the base "outside that pull request", for example by a direct push to the default branch, "even if branch protection rules on that pull request were not satisfied" (https://docs.github.com/en/pull-requests/reference/pull-request-merges); `develop` is the default branch in all thirteen. And a protected branch accepts a push of commits that have passed its required checks: "Pull requests that are up-to-date and pass required status checks can be merged locally and pushed to the protected branch" (troubleshooting page above). "Draft pull requests cannot be merged" (https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

## 5. Recorded positions the proposal must name

Releases and the cascade:

- `docs/releases.md:132`: "The cascade is **manual on purpose** (a small number of commands at a moment the user is already at the keyboard; an auto-PR version was considered and declined)." Present since the initial commit (`1dc252e`, 2026-06-14).
- `docs/releases.md:89`: the promotion "is **not** a reviewed PR: the repo is squash-only, so this merge commit is made locally as part of the release".
- `docs/releases.md:146`: the open cycle is "a direct push — exempt from `version-guard.yml`, like the back-merge itself".
- `docs/ci.md:26`: "**let admins bypass** — the release flow's back-merge (`main→develop`) and promotion (`develop→main`) are direct pushes, not PRs". `docs/ci.md:129`: "(The release back-merge to `develop` is a direct push, not a PR, so it isn't subject to this.)" `templates/.github/workflows/version-guard.yml:5-6` says the same.
- `docs/ci.md:48`: because the repository is squash-only, `develop → main` is done from the CLI; "don't add a PR-required ruleset to `main` without rethinking this".

The decided helper:

- `docs/in-flight_ideas.md:48-49`, "Branching: keep two trunks, automate the tax": "Decided: keep the permanent `develop`+`main` model, not release-from-main. Instead automate the back-merge cascade (a `git back-merge` dev-tool) and harden the promotion against a stale local `develop`; record the keep-two-trunk choice as an ADR. [D1]"
- `docs/handbook-improvements_ideas.md:310` (D1, decided 2026-07) and `:312`: the `git back-merge` helper "pull `main`, merge it down to `develop` with `--no-ff` …, push, open the next dev cycle via the existing `git dev-release --open` (code repos only …), and fan `develop` out to each open working worktree", with a promotion staleness guard, folded into the release skill (C2, `:297`), "while the irreversible tag push stays the explicit human step". `:316` lists D1 as "decided: keep two trunks; remaining work is automating the cascade".
- The pull-request title check the proposal's title rule resembles is A11, `docs/handbook-improvements_ideas.md:250`, indexed at `docs/in-flight_ideas.md:51-52`.

Who merges, and what a release ask covers:

- `docs/ai-collaboration.md:22`: "merging a feature PR into `develop`, tagging, and releasing write to shared state and need explicit authorization."
- `docs/ai-collaboration.md:25`: "**Feature PR → `develop` is the user's merge.** A human reviews and squash-merges it".
- `docs/ai-collaboration.md:26`: "Prompt for a release after every `develop` merge."
- `docs/ai-collaboration.md:27`: release authorisation "is its own explicit, per-release ask"; `:28`: "That one release ask authorises the whole CLI flow — including the `develop → main` promotion …, bump, tag, push, and back-merge cascade." `:32`: after a release, run the cascade. `:33`: "Never force-push `main`/`develop` …; never bypass the release gate."
- `templates/CLAUDE.md.template:9` and `templates/AGENTS.md.template:9`: "**Merging a PR into `develop` is the user's call.**" (not restricted to feature pull requests); line 14 of both: "PRs are **squash-merged**".
- `docs/branching.md:70-71` ("Who merges"): a human reviews and squash-merges feature pull requests; `develop → main` is done from the CLI under one release authorisation.
- `docs/agents.md:51`: "Deterministic sequences are not agents. … the cascade: … those live in `dev-tools` and in skills."

The northstar:

- Squash merging, `docs/northstar.md:24`: "every pull request is squash-merged with a Conventional Commit title, which is what the changelog is generated from".
- Dependencies between repositories, `docs/northstar.md:16`: "Try hard to avoid dependencies between repos."; `:32`: "Dependencies *between* repos are avoided for the same reason: they make one repo's build depend on another's state"; `:26`: "a change to one never breaks another".
- Gates, axiom 4, `docs/northstar.md:62`: "**Automate the mechanical; gate the irreversible.** Changelogs and releases are scripted and verified by a CI gate — *and* merging to a shared trunk, tagging, and releasing still require an explicit human hand." Also `:44` and `:50` ("asked for per action rather than inferred"), and `:8` (a change of intent is made in the northstar in the same pull request as the convention).

Branching:

- Working-branch prefixes, `docs/branching.md:19-34`: `:21` "Working branches are named `<prefix>-<short-description>`, **hyphen not slash**"; the table maps `feature-`, `bug-`/`fix-`, `doc-`, `test-`, `ops-`, `ci-`, `build-`, `release-` to Conventional Commit types; `release-` is "the `release vX.Y.Z` bump commit … dropped". No back-merge prefix exists.
- After-merge cleanup, `docs/branching.md:73-107`: the sync belongs to whoever merged, "the release promotion and the back-merge, which have no PR author at all" (`:75`); `:94` "A squash merge breaks the ancestry test" and the rule to verify from the pull request and delete with `-D` (`:98-104`).
- Tracking when a feature was added, `docs/branching.md:58-64`: `:62` "`git log --first-parent develop` is one line per squash commit (one per feature) plus one back-merge commit per release … This holds because the cascade merges `main` into `develop` with `--no-ff` … In this handbook the cascade fast-forwarded from v0.8.5 to v0.14.0"; `:63` per release by `--first-parent main`; `:64` tags and changelog sections.
- `docs/repo-layout.md:79-87`: "Never commit in `<repo>-main` / `<repo>-develop`" (the release flow commits there regardless: promotion and bump in `-main`, back-merge and open cycle in `-develop`).

Cross-repository reads:

- `docs/docs-site.md:112`: "This is the one place a workflow reads another ParkviewLab repo, and the pin is what keeps it within the northstar's rule against depending on another repo's state: an exact released tag is a locked dependency, not a live one". `docs/ci.md:161`: "a workflow never checks `dev-tools` out at a branch." A back-merge check shipped in dev-tools and checked out by the version guard would be a second such place; carried inline in the version-guard template, it would not.

## 6. The back-merge check, simulated

The check is `sim/backmerge-check.sh <base-sha> <head-sha> [<main-ref>] [<tag>]`. It implements the specified conditions and four additions, each exercised below:

1. The commits in base..head not reachable from `main` are exactly one merge commit M, optionally followed by one commit C that is the head and whose parent is M. (Addition: any other commit not on `main`, below or above M, is refused, not only extra merges.)
2. M has two parents; M^1 is an ancestor of base; M^2 is an ancestor of `main`.
3. The tree of M equals `git merge-tree --write-tree M^1 M^2`, and that automatic merge is clean (exit 0). A conflicting automatic merge is refused even if the hand resolution looks right.
4. The version at M equals `main`'s (addition). Without C, head's version equals `main`'s. With C, C changes only version lines, only in the source-of-truth file and its lockfile, only from `main`'s version to the next-patch placeholder as `_sot.sh` computes it for `git dev-release --open` from a plain version: X.Y.(Z+1).dev0 for `pyproject.toml`, X.Y.(Z+1)-dev0 for `package.json`, X.Y.(Z+1)-dev for `VERSION.txt`. A lockfile that records the project's version must move with it (addition), and in `uv.lock` or `package-lock.json` the changed line must belong to the project itself, not a dependency.
5. Optional tag mode (addition): every commit M brings from `main` is in the named tag or is that tag's changelog commit ("docs(changelog): <tag> [skip ci]", touching only `CHANGELOG.md`), and `main`'s version equals the tag's. Without it, "on `main`" is accepted as released, and `main` accepts direct pushes (unprotected in eleven repositories).
6. It refuses a shallow repository outright (item 7).

The history built in `sim/run-sim.sh`, with dev-tools' real `git-bump`, `git-release` and `_sot.sh` (so the placeholder arithmetic and `uv version`'s lockfile rewrite are the production code): v0.1.0 on `main`; `develop` opened at 0.1.1.dev0; feature A by squash; the release (`git merge --no-ff develop` on `main`, `git bump patch`, `git release`, push); the changelog commit by github-actions[bot] on `main` after the tag; feature F merged into `develop` during the release; then `back-merge-v0.1.1` from `origin/develop` with `git merge --no-ff origin/main` (M) and the open-cycle commit (C, 0.1.1 to 0.1.2.dev0 in `pyproject.toml` and `uv.lock`).

| Case | Expected | Result and reason given |
|---|---|---|
| Clean back-merge, head = M | pass | pass |
| Clean back-merge with the open-cycle commit, head = C | pass | pass |
| The same, tag mode | pass | pass |
| Extra commit after M | reject | "open-cycle version 0.1.1 is not main's next-patch placeholder 0.1.2.dev0" |
| Extra commit after C | reject | "3 commits not on main in base..head" |
| Open-cycle commit that also edits another file | reject | "the open-cycle commit changes app.txt" |
| Extra commit below M (branch commit, then merge) | reject | "a second commit not on main sits below the merge" |
| Merge with an edit folded in (altered tree) | reject | "tree … differs from the automatic merge of its parents" |
| Merge of a commit on top of `main` that `main` lacks | reject | "a second commit not on main sits below the merge" |
| Merge of a working branch | reject | same |
| Open-cycle commit sets 0.1.2.dev1, 0.2.0.dev0, 0.1.2, or 0.1.1.dev0 | reject (4 cases) | "open-cycle version … is not main's next-patch placeholder 0.1.2.dev0" |
| Placeholder in `pyproject.toml`, `uv.lock` left at 0.1.1 | reject | "uv.lock still records 0.1.1 for the project" |
| Merge of an older `main` commit (the promotion, before the bump) | reject | "version at the merge (0.1.1.dev0) is not main's (0.1.1)" |
| No merge: head is `main`'s `[skip ci]` changelog commit (a fast-forward) | reject | "found 0" merges |
| A commit pushed straight to `main` after the tag, carried by the back-merge | pass in plain mode; reject in tag mode | tag mode: "was pushed to main after v0.1.1 and is not its changelog commit" |
| Refresh: PR G merges into `develop`; old head against the new base | pass, but not up to date | the conditions hold; `git merge-base --is-ancestor <new base> <old head>` is false, so strict protection keeps the button disabled (eleven repositories) |
| Refresh by GitHub's "Update branch" (merge `develop` into the branch) | reject | "found 2" merges |
| Refresh by rebuilding `back-merge-v0.1.1` from the new `develop`, force-pushed | pass (tag mode) | and the rebuilt head contains the new base |
| Conflict: a dev build (0.1.1.dev1) lands on `develop` during the release | reject | `git merge` conflicts in `pyproject.toml` and `uv.lock`; resolved by hand to `main`'s version, the check says "the automatic merge of the parents conflicts" |
| Evaluated after the guard's `git fetch --depth=1 origin develop` | refused | "shallow repository" |

`sim/run-sim-kinds.sh` repeats the pass, pass, reject pattern for a `package.json` repository (3.5.1 to 3.5.2-dev0, `package.json` and both root version lines of `package-lock.json`) and a `VERSION.txt` repository (0.23.1 to 0.23.2-dev); a placeholder re-pointed to the next minor is refused in both.

What the simulation shows about the refresh. A head built before `develop` moved still satisfies every condition against the new base, because the conditions concern only what the branch brings. What stops it is strict protection, and both ways GitHub offers to update the branch add commits the check refuses (an update merge is a second merge not on `main`; an update rebase replays `main`'s release commits as new commits not on `main`). Rebuilding the branch from the new `develop` and force-pushing it keeps the one-merge shape and passes. In pensa-grex and pensa-forma, where `strict` is false, the stale head could be merged as it is; GitHub's own merge would then carry the newer `develop`, and the back-merge's content would still be exactly as checked.

What the check should do on a conflict. Refuse, as it does, and leave the resolution to a person. The case has never occurred: none of the 217 merges in the thirteen histories, and none of the 31 back-merge merge commits, differs from or conflicts in its automatic merge. The simulation shows the one realistic cause: a version change on `develop` between the promotion and the back-merge (an on-demand dev build, or an open cycle run before the back-merge landed), which conflicts on the version line of the source-of-truth file and its lockfile. That cause is preventable before the merge is attempted: the helper can refuse while `develop`'s version differs from the version that was promoted, and `git dev-release` can refuse while the newest `v*` tag is not an ancestor of `develop`. Accepting hand resolutions in the check would add a rule for a case with no recorded occurrence.

Wiring it into a workflow (derived from items 4 and 7; not run on GitHub):

- Evaluate on explicit SHAs: base `$(git rev-parse HEAD^1)` from the synthetic merge (or `github.event.pull_request.base.sha`, with the caveat in item 4), head `github.event.pull_request.head.sha`. Evaluated on HEAD, the synthetic merge would itself be a second merge not on `main` (the earlier review's `review-sim/scenario1.sh` showed two).
- Keep `fetch-depth: 0` and drop the `git fetch --depth=1` line (item 7). `merge-tree --write-tree` writes tree objects, so the checkout must be writable (true on a runner; a read-only mount failed in the bash 5 replay until the repository was copied).
- Select the mode inside the one required job, `no-version-change`, by `github.head_ref`. A second job selected by `if:` would report success when skipped, so a pull request could satisfy the required context by its branch name alone unless both jobs were required.
- The head commit must not carry `[skip ci]`; M and C never do, and `--no-ff` guarantees the head is not `main`'s changelog commit.
- The branch name `back-merge/<tag>` conflicts with `docs/branching.md:21`; `back-merge-<tag>` follows it, and the prefix table would gain a row.

An option these facts admit and the earlier proposal did not consider: land the verified back-merge by a fast-forward push instead of the merge button. The pull request exists only to run the required checks on its head; once they pass, `git push origin <head-sha>:develop` fast-forwards `develop` to the head, which leaves `develop`'s first-parent line exactly as today's `--no-ff` back-merge does (C, then M, then the previous `develop` tip), and GitHub marks the pull request merged because its head became reachable from the default branch. Opened as a draft, the pull request offers no merge button at all, so it cannot be squashed. If GitHub accepts that push without the bypass (the documentation says a protected branch accepts commits that have passed its required checks, and the checks are recorded against the head SHA), the back-merge proposal no longer depends on enabling merge commits, and the two proposals separate cleanly. Unverified: whether the push is accepted without the administrator bypass in practice, and whether a draft pull request is marked merged indirectly. Both need a trial in a scratch repository with the same protection before the proposal relies on them.

## 7. The version guard's depth-one fetch

Every one of the thirteen version-guard copies checks out with `fetch-depth: 0` and then runs `git fetch --no-tags --depth=1 origin "$BASE"` (template lines 19-21 and 26). The first step already fetched every branch and tag in full (the run log shows `+refs/heads/*:refs/remotes/origin/* +refs/tags/*:refs/tags/*` and the pull merge ref). The second writes `develop`'s tip into `.git/shallow`, so git treats that one commit as having no parents. No object is deleted; what changes is every answer that has to walk through `develop`'s tip. (`git rev-list --all` is unchanged in case 1 below and one lower in case 2, where one commit becomes unreachable.)

Reproduced in `sim/shallow-repro.sh` with the handbook's history and an Actions-style checkout of a synthetic pull merge ref:

| Measure | Case 1 before | Case 1 after | Case 2 before | Case 2 after |
|---|---|---|---|---|
| Commits reachable from `origin/develop` | 126 | 1 | 123 | 1 |
| From `origin/main` | 125 | 125 | 125 | 124 |
| From tag v0.23.1 | 125 | 125 | 125 | 124 |
| `v0.23.0` is an ancestor of `origin/develop` | yes | no | yes | no |
| `git merge-base origin/develop origin/main` | `4b572e0` | none | `67f9d65` | `67f9d65` |

Case 1 is today's refs (`develop` at the back-merge `502dadc`, not an ancestor of `main`). Case 2 is the release window (`develop` at `67f9d65`, the commit promoted for v0.23.1 and so an ancestor of `main`); there `main` and the new tag also lose history (the previous back-merge `c0e5523` becomes unreachable, and `git fsck` reports it dangling and the commit-graph inconsistent with the shallow boundary). The reproduction in `sim/run-sim.sh` shows the effect on the back-merge check when a feature landed during the release (the case the pull request exists for): `git merge-base M^1 M^2` returns nothing, `git merge-tree --write-tree M^1 M^2` fails with "refusing to merge unrelated histories", and an earlier `develop` commit is reported as not an ancestor of `origin/develop`. The current guard is unaffected, because it only reads `origin/$BASE:<file>`, the tip's own tree; the fetch is redundant for it, since the checkout already fetched `develop`.

Precisely: after the fetch, `origin/develop` (and `FETCH_HEAD`) has a history of one commit; ancestry tests against `develop` fail for every commit but its tip; merge bases involving `develop`'s tip are lost unless that tip is itself reachable from the other side; and when `develop`'s tip is an ancestor of `main`, as it is between a promotion and its back-merge, `main` and any tag after the promotion lose the history reachable only through that tip.

## Open questions for the proposal

- Whether a fast-forward push of a checked head to `develop` is accepted without the administrator bypass, and whether a draft pull request is then marked merged (item 6); both are testable only by changing a scratch repository.
- Whether the check is inlined in the version-guard template or shipped from dev-tools, given `docs/docs-site.md:112` and `docs/ci.md:161`.
- Whether tag mode is required, given that `main` is unprotected in eleven repositories and has taken two force pushes.
- Whether dev versions stay committed, and if so whether only the open-cycle placeholder is committed (item 2).
- Whether a no-bypass tag ruleset is wanted, given six recorded tag deletions, most of them re-creations after a failed release.
