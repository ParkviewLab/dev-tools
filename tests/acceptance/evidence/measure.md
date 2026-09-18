# The changelog list rule, measured as designed

Second measurement for the proposal "One changelog generator", made on 2026-09-17. It replaces the figures of the first prototype (proposed_list.py), which the review found do not describe the rule the design adopts (findings F29 to F34 and F46 to F49).

## Scope and sources

The ten ParkviewLab repositories that have released with a per-repository generator: pensa-grex, deco-assaying, smalt-mcp, ebony-enriching, conception-space, flint-slating, jonobones, paper-boxing, cobalt-grinding and cogrind-workshop. Releases are the 81 tags matching `^v[0-9]+\.[0-9]+\.[0-9]+$`, sorted by version. The history was read from full clones made for this measurement (revise/clones); the merged pull requests (231) from `gh pr list --state merged --limit 1000 --json number,title,body,mergeCommit,baseRefName,headRefName,mergedAt`; the published notes from `gh release view <tag> --json body` for the 50 tags that have a GitHub Release, and otherwise from the tag's section of CHANGELOG.md on origin/main. Everything was computed by script, except the judgements on the Highlights paragraphs in Part three, which are stated as mine; the scripts are listed at the end.

Definitions used throughout. Truth: the pull requests whose merge commit, as GitHub records it (`mergeCommit.oid`), is in the release's range under R1. Expected: the truth less the carrier pull requests of R3. Listed: what proposed_list2.py lists.

## Results in brief

The rule as designed lists exactly the expected pull requests in 79 of the 81 releases. The other two are conception-space v0.8.2 and v0.8.3: #11 and #12 were cherry-picked onto the release line for v0.8.2, so the rule lists them there and not again in v0.8.3, whereas the truth places their merge commits in v0.8.3. That is the behaviour the design intends; no release has an unexplained difference. Across the 81 ranges the rule accounts for all 601 commits: 202 pull-request commits, 64 commits absorbed into the real merges that contain them, 261 bookkeeping commits, 72 direct commits, and the 2 original commits of #11 and #12 in v0.8.3.

On the published side, 122 of the 202 expected pull requests are absent from the published lists by number (5 of them were published by commit hash), and 34 published list lines correspond to no pull request (32 are the release job's own changelog commits, 2 are real changes made without a pull request). A re-run of git-cliff with each repository's own configuration reproduces all 76 published sections exactly, so both defects are properties of the current generator. In a sample of eight releases, the Highlights paragraphs describe 49 of the 70 pull requests their lists omitted, and every specific claim checked is traceable to the release's commits.

In a synthetic repository with squash merges, real merges, a cherry-pick onto the release line, local promotions, a back-merge pull request, bookkeeping commits and one direct commit, the rule lists exactly what was stated in advance for both tags.

Four points in the rule text need a decision before the design text is final: R3's "base branch is main" clause also catches a feature pull request into main (D9); R2(c) does not see a real merge picked commit by commit (D8); R6 takes a squash's title at merge time but a default-title merge's current title from the API (D17); and R5 does not say what an empty commit is (D14).

## Part one: the implementation

proposed_list2.py (python3, standard library, git and gh) takes a repository directory, the previous tag or `-`, the tag and the pull-request JSON, and prints JSON: the listed pull requests by group with the commits and the route by which each was recognised, the direct commits, every bookkeeping commit with its reason, the carriers and already-shipped pull requests left out, the commits absorbed into each real merge, warnings, and the rendered section. `--markdown` prints the section alone.

What needs the GitHub API, and what works from git alone:

- R3: the base and head branch of each pull request.
- R6: the title of a pull request merged at GitHub's default title (see D17 for a git-only alternative).
- R7: the pull-request body.
- Optional cross-check: a GitHub-made commit ending in '(#N)' that is not the merge commit GitHub records for #N is reported (none in the data).

From git alone: R1 ranges; R2 (a), (b) and (c) including patch-ids and trailers; R4; R5 (i), (ii) and (iii); R6 for squash, titled merges and cherry-picks; R7 for titles and commit messages.

### Decisions and ambiguities

Each entry names the rule, the question the text leaves open, what the implementation does, and the evidence from the data. The design text can be made precise by adopting or amending each decision.

D1 (R1). Which tag is 'the previous tag'? Decision: The highest tag below this one, among tags matching ^v[0-9]+\.[0-9]+\.[0-9]+$, ordered by the three numbers. Evidence: For all 81 tags this equals `git describe --tags --abbrev=0 <tag>^`, which the current generator uses, and every earlier tag is an ancestor of every later one. The two definitions differ only if release lines diverge; the design text should name one.

D2 (R1). Why the first-release form matters. Decision: `git rev-list <tag>`. Evidence: The current generator passes `..<tag>` to git-cliff; `..<tag>` means `HEAD..<tag>`, which is empty whenever HEAD is the tag or a descendant of it. Re-running git-cliff over `..<tag>` gives an empty list for all 10 first releases; over `<root>..<tag>` it lists 42 of the 61 pull requests those releases omitted (the other 19 are dropped by the filters).

D3 (R2). What is 'anywhere in the repository's history'? Decision: Every commit reachable from any ref of the clone (`git log --all`: remote-tracking branches and tags). Evidence: A CI checkout must therefore fetch all branches and tags (actions/checkout with fetch-depth: 0). A GitHub-made commit that lives only on a deleted branch is invisible: smalt-mcp #41 was merged into the since-deleted claude branch and its merge commit 9480437 is in no fetched ref. No listing in the measured history depends on such a commit.

D4 (R2(a)). Shape of a squash commit. Decision: Committer email noreply@github.com, exactly one parent, first line ending in '(#N)'; if the first line carries several, the last is taken. Evidence: GitHub is also the committer of commits that are not pull-request merges: the root commits GitHub made when five repositories were created ('Initial commit', 'Add woot.md with initial content') and Dependabot's branch commits (deco-assaying f36d25c, baa63f5). None ends in '(#N)', so none is attributed; the root commits are direct commits.

D5 (R2(b)). Which commits are a real merge's own commits, and what if another pull request's commit is among them? Decision: `git rev-list P2 [P3 ...] ^P1`, intersected with the range. A GitHub-made commit of another, non-carrier pull request among them is still that pull request (listed on its own); everything else among them (branch commits, local merges, carrier merges) belongs to the enclosing pull request and is never listed on its own. Evidence: 64 commits are absorbed this way across the ten repositories. The only nested case in the data is smalt-mcp #38, which contains carrier #37's merge 8f0fb81; it is absorbed. No non-carrier pull request is nested inside another, so the first half of the decision is exercised only by construction.

D6 (R2(c)). How patch-ids are computed, and in what order the two tests run. Decision: Non-merge commit: `git patch-id --stable` over `git log -p --no-renames`. GitHub-made merge: over `git diff --no-renames M^1 M`, which is what `git cherry-pick -m 1 M` applies. The '(cherry picked from commit X)' trailer is tested first, then the patch-id. A merge is never taken to be a cherry-pick. If several pull requests share a patch-id, the lowest number is taken. Evidence: The two conception-space picks (ad6975c, 1681b10) carry no trailer and are recognised by patch-id. `git cherry-pick -m 1` of a real merge is recognised in the supplementary synthetic scenario. No patch-id is shared by two pull requests in the data.

D7 (R2(c)). Can a commit be a cherry-pick of a carrier pull request? Decision: Carrier pull requests are left out of the patch-id index, so no commit is taken to be a cherry-pick of one. Evidence: In 12 carrier merges the first-parent diff equals the diff of a single commit, because the carrier brought exactly one change (for example cogrind-workshop #1 and 958c3f5, smalt-mcp #36 and #37 and the 'release v1.2.0' commits). Without the exclusion those commits would be attributed to the carrier and vanish from the list; in the data that would drop cogrind-workshop 958c3f5.

D8 (R2(c)). A real-merge pull request picked commit by commit. Decision: Not recognised by the rule as written; the picks are direct commits and the pull request is listed again when its merge reaches a release. Evidence: Supplementary synthetic scenario, #3: v1.0.0 lists 'exporter: module' and 'exporter: wiring' under Direct commits and v1.1.0 lists #3. The measured history contains no such pick. Either prescribe `git cherry-pick -m 1 <merge>` for hotfixes, or extend R2(c) so that a pull request whose own commits' patch-ids all occur in an earlier release counts as shipped there.

D9 (R3). Is every pull request whose base branch is main a carrier? Decision: Implemented as written; the clause misclassifies one pull request. Evidence: cogrind-workshop #1 (ci-node24-action-pins into main) is a real change; R3 leaves it out and its one commit, 958c3f5 'ci: bump action pins to Node 24', appears under Direct commits. The other 21 carriers all have head develop or main. With the base-main clause removed, cogrind-workshop v0.1.0 lists #1 under Maintenance (checked). No pull request in the data has a head branch beginning 'back-merge'; that clause serves the proposed flow only.

D10 (R3). What does 'as if it were not there' do to the carrier's own merge commit? Decision: A carrier merged for real is treated as a merge that is not a pull-request merge: its merge commit is tested under R5(iii), and its own commits are not absorbed but examined one by one. A carrier merged by squash cannot be handled (the changes it carries are not in the range as separate commits); the script leaves it out with a warning. Evidence: 21 carrier merge commits tested, all equal to the automatic merge of their parents; the 22nd, smalt-mcp #37, lies inside #38 and is absorbed. All 22 carriers are real merges, so the squash case does not occur.

D11 (R4). What is 'reachable from the previous tag', and is only the previous tag consulted? Decision: Attribution under R2 (a, b, c) over every commit of `git rev-list <prev>`, the whole ancestry of the previous tag; only the version-previous tag is consulted. Evidence: With diverging release lines a pull request shipped on another line could be listed again; 'reachable from any earlier tag' would avoid that. In the measured history every earlier tag is an ancestor of every later one, so the two readings agree. R4 acts twice: conception-space v0.8.3 does not list #11 and #12, shipped by cherry-pick in v0.8.2.

D12 (R5(i)). When does a diff 'change only the version value'? Decision: Version files are recognised at the repository root only. A file passes if every line the diff changes matches ^\s*"?version"?\s*[:=] and the parsed file, with the project's own version removed, is identical before and after. The project's own lockfile entry is the uv.lock [[package]] whose source is editable or virtual '.', or whose name equals [project].name (names normalised); the Cargo.lock [[package]] named as [package].name; the top-level and packages[""] version in package-lock.json. A version file that is added or deleted fails. Lockfile-only version changes pass. Evidence: 112 commits recognised ('release vX' 67, open-cycle 36, 'chore: dev build' 4, jonobones 'version X' 3, one 'ops: bump version', one 'Revert "release v1.2.0"'). conception-space's bumps, which touch package.json and package-lock.json, are recognised. The synthetic dependency pin (pyproject.toml dependency and uv.lock specifier) is listed under Direct commits. Neither failure mode of F46 occurs.

D13 (R5(ii)). Which CHANGELOG.md, and what about root commits? Decision: The root-level CHANGELOG.md, added, modified or deleted. A root commit is compared with the empty tree, so it is bookkeeping only if it adds nothing but CHANGELOG.md. Evidence: 40 commits, all 'docs(changelog): vX [skip ci]'. The first commit of each of the ten repositories adds project files and is listed under Direct commits (10 of the 72).

D14 (R5). An empty commit (no diff). Decision: Neither (i) nor (ii) applies, so it is listed under Direct commits, as the rule is written. Evidence: None occurs in the data. The design text should say whether an empty commit is bookkeeping.

D15 (R5(iii)). How the automatic merge is computed and a difference reported. Decision: `git merge-tree --write-tree` of the first two parents. A conflicted automatic merge never equals the merge; a merge with more than two parents is not bookkeeping. The difference is reported as `git diff --stat <automatic tree> <merge tree>`. Evidence: 109 merges examined in the ten repositories (88 that are not pull-request merges, 21 carrier merges): every tree equals the automatic merge, so no merge in the measured history carries changes of its own. The synthetic merge with an extra edit is listed under Direct commits with 'src/b.py | 2 +-'.

D16 (R6). What counts as a recognised type? Decision: Header ^type(scope)?!?: followed by a blank, type letters only and matched case-insensitively. Anything else is Other changes, shown in full. Evidence: 43 of the 202 listed pull requests fall under Other changes: titles such as 'C-1: ...', 'B-3: ...', 'tools: ...', 'search: ...', 'cleave: ...', 'Dockerfile: ...', 'schema+tools: ...'. GitHub's default revert title 'Revert "..."' has no type and would go under Other changes, not Reverts as cliff.toml's ^Revert rule put it; no revert pull request exists in the data.

D17 (R6). Title at merge time or current title? Decision: As written: the first line of a squash or titled merge (the title at merge time), and the API title for a merge at GitHub's default title (the current title). Evidence: smalt-mcp #3, #6 and #11 were retitled 18 s, 22 min 16 s and 3 min 36 s after their default-title merges; their merge bodies keep the earlier titles, so the listed title follows later edits and cannot be regenerated from git. The merge body's first line equals the API title in 68 of 71 default-title merges; a squash's first line differs from the API title in 3 of 159 (ebony-enriching #17, flint-slating #6, conception-space #2). No group changes in the data. Taking the title at merge time from git in both cases would make R6 independent of the API.

D18 (R7). Where is a BREAKING CHANGE line sought, and where is a breaking pull request listed? Decision: At the start of a line, case-sensitive, in the pull request's squash, merge or pick commit message, in every own commit of a real merge, and in the pull-request body. A breaking pull request is listed once, under Breaking changes. The major-version warning fires when the major number exceeds the previous tag's, never for a first release. Evidence: 5 breaking pull requests, pensa-grex #65 to #69 in v3.0.0, all by '!'. Warnings for pensa-grex v2.0.0 and smalt-mcp v1.0.0; smalt-mcp's breaking change is stated only in prose in a commit body ('major bump; breaking change to ...'), which R7 does not read. The synthetic #3 is breaking through a footer in one of its branch commits.

## Part two: the rule against the truth

### Per repository

"Exact + explained" counts releases in which the rule lists exactly the expected pull requests, plus releases whose differences are all explained as intended behaviour.

| Repository | Tags | Commits in ranges | Truth | Carriers | Expected | Listed | Missing | Extra | Exact + explained | Direct commits | Absorbed into real merges | Bookkeeping |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pensa-grex | 19 | 181 | 97 | 0 | 97 | 97 | 0 | 0 | 19 + 0 | 4 | 0 | 80 |
| deco-assaying | 16 | 87 | 19 | 4 | 15 | 15 | 0 | 0 | 16 + 0 | 31 | 8 | 33 |
| smalt-mcp | 12 | 101 | 42 | 12 | 30 | 30 | 0 | 0 | 12 + 0 | 1 | 36 | 34 |
| ebony-enriching | 11 | 61 | 22 | 5 | 17 | 17 | 0 | 0 | 11 + 0 | 1 | 12 | 31 |
| conception-space | 7 | 48 | 22 | 0 | 22 | 22 | 2 | 2 | 5 + 2 | 1 | 0 | 23 |
| flint-slating | 6 | 30 | 8 | 0 | 8 | 8 | 0 | 0 | 6 + 0 | 1 | 8 | 13 |
| jonobones | 6 | 70 | 3 | 0 | 3 | 3 | 0 | 0 | 6 + 0 | 29 | 0 | 38 |
| paper-boxing | 2 | 16 | 9 | 0 | 9 | 9 | 0 | 0 | 2 + 0 | 1 | 0 | 6 |
| cobalt-grinding | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1 + 0 | 1 | 0 | 1 |
| cogrind-workshop | 1 | 5 | 2 | 1 | 1 | 1 | 0 | 0 | 1 + 0 | 2 | 0 | 2 |
| Total | 81 | 601 | 224 | 22 | 202 | 202 | 2 | 2 | 79 + 2 | 72 | 64 | 261 |

### Every case that is not exact

- conception-space v0.8.2, #11 extra: R2(c): listed as a cherry-pick (ad6975cd0d of 27106668c6); GitHub's merge commit 27106668c6 first reaches a release in v0.8.3.
- conception-space v0.8.2, #12 extra: R2(c): listed as a cherry-pick (1681b107dd of e3f7a7dc40); GitHub's merge commit e3f7a7dc40 first reaches a release in v0.8.3.
- conception-space v0.8.3, #11 missing: R4: already shipped in an earlier release by ad6975cd0d (cherry-pick (patch-id)); GitHub's merge commit 27106668c6 lies in this range.
- conception-space v0.8.3, #12 missing: R4: already shipped in an earlier release by 1681b107dd (cherry-pick (patch-id)); GitHub's merge commit e3f7a7dc40 lies in this range.

Both cases are correct behaviour. ad6975c and 1681b10 are copies of GitHub's squash commits 2710666 (#11) and e3f7a7d (#12), made on the release line minutes after the originals merged into develop; they carry no "(cherry picked from commit ...)" trailer and are recognised by `git patch-id --stable` alone. The originals reached a release only in v0.8.3, when develop was next promoted, and R4 keeps them out of that list.

### Per release

| Repository | Tag | Commits | Truth | Carriers | Expected | Listed | Missing | Extra | Direct | Bookkeeping |
|---|---|---|---|---|---|---|---|---|---|---|
| pensa-grex | v1.0.0 | 39 | 36 |  | 36 | 36 |  |  | 1 | 2 |
| pensa-grex | v1.0.1 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| pensa-grex | v1.0.2 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| pensa-grex | v1.1.0 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| pensa-grex | v1.2.0 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| pensa-grex | v1.3.0 | 12 | 8 |  | 8 | 8 |  |  | 0 | 4 |
| pensa-grex | v1.3.1 | 7 | 3 |  | 3 | 3 |  |  | 0 | 4 |
| pensa-grex | v1.3.2 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| pensa-grex | v2.0.0 | 8 | 4 |  | 4 | 4 |  |  | 0 | 4 |
| pensa-grex | v2.1.0 | 7 | 3 |  | 3 | 3 |  |  | 0 | 4 |
| pensa-grex | v3.0.0 | 14 | 10 |  | 10 | 10 |  |  | 0 | 4 |
| pensa-grex | v3.1.0 | 9 | 1 |  | 1 | 1 |  |  | 3 | 5 |
| pensa-grex | v3.2.0 | 8 | 3 |  | 3 | 3 |  |  | 0 | 5 |
| pensa-grex | v3.2.1 | 6 | 1 |  | 1 | 1 |  |  | 0 | 5 |
| pensa-grex | v3.2.2 | 6 | 1 |  | 1 | 1 |  |  | 0 | 5 |
| pensa-grex | v3.3.0 | 12 | 7 |  | 7 | 7 |  |  | 0 | 5 |
| pensa-grex | v3.4.0 | 7 | 3 |  | 3 | 3 |  |  | 0 | 4 |
| pensa-grex | v3.5.0 | 7 | 3 |  | 3 | 3 |  |  | 0 | 4 |
| pensa-grex | v3.5.1 | 14 | 9 |  | 9 | 9 |  |  | 0 | 5 |
| deco-assaying | v0.1.0 | 24 | 0 |  | 0 | 0 |  |  | 24 | 0 |
| deco-assaying | v0.1.1 | 1 | 0 |  | 0 | 0 |  |  | 1 | 0 |
| deco-assaying | v0.1.2 | 1 | 0 |  | 0 | 0 |  |  | 1 | 0 |
| deco-assaying | v0.1.3 | 1 | 0 |  | 0 | 0 |  |  | 1 | 0 |
| deco-assaying | v0.1.4 | 1 | 0 |  | 0 | 0 |  |  | 1 | 0 |
| deco-assaying | v0.1.5 | 1 | 0 |  | 0 | 0 |  |  | 1 | 0 |
| deco-assaying | v0.1.6 | 7 | 2 | #2 | 1 | 1 |  |  | 2 | 2 |
| deco-assaying | v0.1.7 | 4 | 2 | #4 | 1 | 1 |  |  | 0 | 2 |
| deco-assaying | v0.2.0 | 4 | 2 | #6 | 1 | 1 |  |  | 0 | 2 |
| deco-assaying | v0.2.1 | 5 | 2 | #9 | 1 | 1 |  |  | 0 | 2 |
| deco-assaying | v0.3.0 | 8 | 3 |  | 3 | 3 |  |  | 0 | 3 |
| deco-assaying | v0.3.1 | 8 | 2 |  | 2 | 2 |  |  | 0 | 6 |
| deco-assaying | v0.3.2 | 7 | 3 |  | 3 | 3 |  |  | 0 | 4 |
| deco-assaying | v0.3.3 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| deco-assaying | v0.3.4 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| deco-assaying | v0.3.5 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| smalt-mcp | v0.1.0 | 13 | 5 | #5 | 4 | 4 |  |  | 1 | 2 |
| smalt-mcp | v0.2.0 | 7 | 3 | #8 | 2 | 2 |  |  | 0 | 2 |
| smalt-mcp | v0.3.0 | 4 | 2 | #10 | 1 | 1 |  |  | 0 | 2 |
| smalt-mcp | v0.4.0 | 8 | 3 | #13 | 2 | 2 |  |  | 0 | 2 |
| smalt-mcp | v0.5.0 | 4 | 2 | #15 | 1 | 1 |  |  | 0 | 2 |
| smalt-mcp | v1.0.0 | 31 | 14 | #30 | 13 | 13 |  |  | 0 | 3 |
| smalt-mcp | v1.1.0 | 7 | 3 | #33 | 2 | 2 |  |  | 0 | 2 |
| smalt-mcp | v1.2.0 | 6 | 2 | #35 | 1 | 1 |  |  | 0 | 4 |
| smalt-mcp | v1.3.0 | 6 | 4 | #36, #37, #39 | 1 | 1 |  |  | 0 | 3 |
| smalt-mcp | v1.3.1 | 5 | 2 | #40 | 1 | 1 |  |  | 0 | 4 |
| smalt-mcp | v1.3.2 | 4 | 1 |  | 1 | 1 |  |  | 0 | 3 |
| smalt-mcp | v1.3.3 | 6 | 1 |  | 1 | 1 |  |  | 0 | 5 |
| ebony-enriching | v0.1.0 | 16 | 7 | #7 | 6 | 6 |  |  | 1 | 2 |
| ebony-enriching | v0.1.1 | 4 | 2 | #9 | 1 | 1 |  |  | 0 | 2 |
| ebony-enriching | v0.1.2 | 4 | 2 | #11 | 1 | 1 |  |  | 0 | 2 |
| ebony-enriching | v0.1.3 | 6 | 3 | #14 | 2 | 2 |  |  | 0 | 2 |
| ebony-enriching | v0.1.4 | 4 | 2 | #16 | 1 | 1 |  |  | 0 | 2 |
| ebony-enriching | v0.1.5 | 3 | 1 |  | 1 | 1 |  |  | 0 | 2 |
| ebony-enriching | v0.1.6 | 4 | 1 |  | 1 | 1 |  |  | 0 | 3 |
| ebony-enriching | v0.1.7 | 4 | 1 |  | 1 | 1 |  |  | 0 | 3 |
| ebony-enriching | v0.1.8 | 6 | 1 |  | 1 | 1 |  |  | 0 | 5 |
| ebony-enriching | v0.1.9 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| ebony-enriching | v0.1.10 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| conception-space | v0.8.0 | 7 | 6 |  | 6 | 6 |  |  | 1 | 0 |
| conception-space | v0.8.1 | 4 | 1 |  | 1 | 1 |  |  | 0 | 3 |
| conception-space | v0.8.2 | 6 | 1 |  | 1 | 3 |  | #11, #12 | 0 | 3 |
| conception-space | v0.8.3 | 7 | 3 |  | 3 | 1 | #11, #12 |  | 0 | 4 |
| conception-space | v0.8.4 | 10 | 5 |  | 5 | 5 |  |  | 0 | 5 |
| conception-space | v0.8.5 | 8 | 4 |  | 4 | 4 |  |  | 0 | 4 |
| conception-space | v0.8.6 | 6 | 2 |  | 2 | 2 |  |  | 0 | 4 |
| flint-slating | v0.1.0 | 6 | 2 |  | 2 | 2 |  |  | 1 | 0 |
| flint-slating | v0.1.1 | 3 | 1 |  | 1 | 1 |  |  | 0 | 0 |
| flint-slating | v0.1.2 | 4 | 1 |  | 1 | 1 |  |  | 0 | 1 |
| flint-slating | v0.1.4 | 5 | 1 |  | 1 | 1 |  |  | 0 | 3 |
| flint-slating | v0.1.5 | 7 | 2 |  | 2 | 2 |  |  | 0 | 5 |
| flint-slating | v0.1.6 | 5 | 1 |  | 1 | 1 |  |  | 0 | 4 |
| jonobones | v0.1.0 | 33 | 0 |  | 0 | 0 |  |  | 17 | 16 |
| jonobones | v0.1.1 | 10 | 0 |  | 0 | 0 |  |  | 4 | 6 |
| jonobones | v0.1.2 | 10 | 0 |  | 0 | 0 |  |  | 4 | 6 |
| jonobones | v0.1.3 | 4 | 0 |  | 0 | 0 |  |  | 1 | 3 |
| jonobones | v0.1.4 | 8 | 0 |  | 0 | 0 |  |  | 3 | 5 |
| jonobones | v0.1.5 | 5 | 3 |  | 3 | 3 |  |  | 0 | 2 |
| paper-boxing | v0.1.0 | 8 | 6 |  | 6 | 6 |  |  | 1 | 1 |
| paper-boxing | v0.1.1 | 8 | 3 |  | 3 | 3 |  |  | 0 | 5 |
| cobalt-grinding | v0.1.0 | 2 | 0 |  | 0 | 0 |  |  | 1 | 1 |
| cogrind-workshop | v0.1.0 | 5 | 2 | #1 | 1 | 1 |  |  | 2 | 2 |

### Direct commits

72 commits reached a release without a pull request and are not bookkeeping. By repository:

| Repository | Direct commits |
|---|---|
| pensa-grex | 4 |
| deco-assaying | 31 |
| smalt-mcp | 1 |
| ebony-enriching | 1 |
| conception-space | 1 |
| flint-slating | 1 |
| jonobones | 29 |
| paper-boxing | 1 |
| cobalt-grinding | 1 |
| cogrind-workshop | 2 |
| Total | 72 |

60 of the 72 are in deco-assaying's first seven releases (31) and jonobones' first five (29, most of them brought in by local `--no-ff` merges of topic branches, whose merge commits are bookkeeping under R5(iii) while their branch commits are listed). The first commit of each of the ten repositories is among the 72. cogrind-workshop 958c3f5 is listed only because R3 treats pull request #1 as a carrier (D9). The column on the right gives the first reason the content test found for not treating the commit as bookkeeping.

| Repository | Tag | Commit | Subject | Why it is not bookkeeping |
|---|---|---|---|---|
| pensa-grex | v1.0.0 | `e9602a5` | chore: initial project scaffold | root commit |
| pensa-grex | v3.1.0 | `baab775` | docs: say plainly that the v3 bookmark shape is only half shipped | changes docs/model_v3_ideas.html |
| pensa-grex | v3.1.0 | `d8f9d8e` | fix(render): keep a hidden card's silhouette instead of painting a zero box | changes src/renderer/src/app.js |
| pensa-grex | v3.1.0 | `551be57` | ci: drop the release job's own changelog commit from the next release's notes | changes cliff.toml |
| deco-assaying | v0.1.0 | `ca34788` | Add woot.md with initial content | root commit |
| deco-assaying | v0.1.0 | `d884c74` | Scaffold parkview-codeparse-server skeleton | changes .gitignore |
| deco-assaying | v0.1.0 | `7e83480` | Implement Python analyzer plus chunking, literals, detectors | changes src/parkview_codeparse/analyze.py |
| deco-assaying | v0.1.0 | `9604db4` | Add full-support analyzers for the remaining v1 languages | changes humans_notes.md |
| deco-assaying | v0.1.0 | `12d9fee` | Wire index_repo end-to-end: walker, source resolver, job pool, manifest | changes src/parkview_codeparse/analyzers/c_family.py |
| deco-assaying | v0.1.0 | `253fe82` | HTTP-route integration tests through the MCP wire protocol | pyproject.toml: a changed line is not a version line |
| deco-assaying | v0.1.0 | `f7db05c` | Partial-clone GitHub fetch + tree.json for full repo inventory | changes src/parkview_codeparse/jobs.py |
| deco-assaying | v0.1.0 | `bfdaa54` | Use --filter=blob:limit=<max_file_bytes> for partial clones | changes src/parkview_codeparse/jobs.py |
| deco-assaying | v0.1.0 | `6334611` | GitHub Trees API pre-flight for accurate sizes of unfetched files | changes src/parkview_codeparse/github.py |
| deco-assaying | v0.1.0 | `885a27f` | README: document the 100 MB peak disk contract | changes README.md |
| deco-assaying | v0.1.0 | `229bafa` | Bin-packed streaming fetch for large GitHub repos | changes src/parkview_codeparse/config.py |
| deco-assaying | v0.1.0 | `137bebf` | GitLab provider: source URL support for gitlab.com repos | changes .claude/scheduled_tasks.lock |
| deco-assaying | v0.1.0 | `04d04d7` | .gitignore: drop accidentally-committed Claude Code state file | changes .claude/scheduled_tasks.lock |
| deco-assaying | v0.1.0 | `d1b2581` | Rename project: parkview-codeparse-server -> deco-assaying | changes README.md |
| deco-assaying | v0.1.0 | `11bcdb7` | admin/stats now reports the server version | changes src/deco_assaying/routes.py |
| deco-assaying | v0.1.0 | `e5fcd66` | Always-managed output: server allocates OUTPUT_ROOT/{job_id} | changes .gitignore |
| deco-assaying | v0.1.0 | `cc04425` | Remove Cobgrind references from prose and docs | changes README.md |
| deco-assaying | v0.1.0 | `1f5ae15` | Download API: GET /outputs/{job_id}/... + DELETE + admin listing | changes src/deco_assaying/jobs.py |
| deco-assaying | v0.1.0 | `0687414` | Retention sweeper: purge job dirs older than OUTPUT_EXPIRY_DAYS | changes src/deco_assaying/retention.py |
| deco-assaying | v0.1.0 | `4ed6b18` | Dockerfile + docker-compose.yml | changes Dockerfile |
| deco-assaying | v0.1.0 | `5978d7d` | Release workflow: multi-arch GHCR image + PyPI on tag push | changes .github/workflows/release.yml |
| deco-assaying | v0.1.0 | `271be83` | README: document Phase 2 — both deployment modes, download API, releases | changes README.md |
| deco-assaying | v0.1.0 | `6f7161b` | Architecture doc: 30-minute orientation for new contributors | changes docs/deco-assaying-architecture.md |
| deco-assaying | v0.1.0 | `540d96f` | README: spell out uv tool / uvx / docker run from GHCR install paths | changes README.md |
| deco-assaying | v0.1.1 | `c260845` | Release v0.1.1: Dockerfile copies README.md so uv sync can read it | changes Dockerfile |
| deco-assaying | v0.1.2 | `4deb7ee` | v0.1.2: artifact-fetch MCP tools so remote LLMs can read job results | changes src/deco_assaying/outputs.py |
| deco-assaying | v0.1.3 | `9f1cab3` | v0.1.3: ergonomics polish on get_manifest and get_tree responses | changes src/deco_assaying/outputs.py |
| deco-assaying | v0.1.4 | `08e6133` | v0.1.4: add MIT LICENSE + SPDX metadata | changes LICENSE |
| deco-assaying | v0.1.5 | `e5bad7a` | v0.1.5: artifact-size index, top-level/all symbols split, gzip, MCP prompts | changes README.md |
| deco-assaying | v0.1.6 | `97f46ea` | Doc: dependency-update automation tradeoffs (deferred) | changes docs/dependency-update-automation.md |
| deco-assaying | v0.1.6 | `f6d34ee` | notes | changes humans_notes.md |
| smalt-mcp | v0.1.0 | `65d412a` | Initial commit | root commit |
| ebony-enriching | v0.1.0 | `d859185` | Initial commit | root commit |
| conception-space | v0.8.0 | `29f84f9` | Initial public release — conception-space (AGPL-3.0-or-later) | root commit |
| flint-slating | v0.1.0 | `b79811b` | Initial commit | root commit |
| jonobones | v0.1.0 | `633ac64` | Initial commit | root commit |
| jonobones | v0.1.0 | `0d7ec66` | M0 derive spike: @joplin/lib runs headless, two profiles sync via filesystem | changes .gitignore |
| jonobones | v0.1.0 | `db186e8` | M1 scaffold: TS+Fastify skeleton, /v1/health, auth hook, config, lockfile | changes .gitignore |
| jonobones | v0.1.0 | `f811ece` | doc-northstar: project intent and axioms | changes docs/northstar.md |
| jonobones | v0.1.0 | `418367d` | ops-ci: GitHub Actions — typecheck, lint, test on PRs and develop | changes .github/workflows/ci.yml |
| jonobones | v0.1.0 | `a401d61` | ops: bump checkout/setup-node to v5 (Node 24 action runtime) | changes .github/workflows/ci.yml |
| jonobones | v0.1.0 | `19e305e` | M2 core data plane: notes/notebooks/tags CRUD per §5.1 conventions | changes src/api/pagination.ts |
| jonobones | v0.1.0 | `4a484d0` | M3: userdata envelope, resources with blobs, search/revisions/conflicts | package-lock.json: a changed line is not a version line |
| jonobones | v0.1.0 | `b41edc9` | M4: sync engine, scheduler, /status, POST /sync, init wizard, CLI controls | changes spike/lib-spike.mjs |
| jonobones | v0.1.0 | `acb53fa` | M5 events: journal, API emitters, post-sync scan, SSE + JSON fallback | package-lock.json: a changed line is not a version line |
| jonobones | v0.1.0 | `01e8dca` | M6 interop proof: round-trip suites against the official joplin CLI | changes .github/workflows/ci.yml |
| jonobones | v0.1.0 | `129706d` | ops-service-install: launchd/systemd user service registration | changes src/cli/commands/service.ts |
| jonobones | v0.1.0 | `d981806` | bug: await journal append in the API write path (event emit race) | changes src/daemon.ts |
| jonobones | v0.1.0 | `bc4c763` | ops-docker: Dockerfile (multi-stage, profile volume, env config) + CI build | changes .dockerignore |
| jonobones | v0.1.0 | `35ddf62` | doc-api: docs/api.md, docs/architecture.md, docs/operations.md | changes docs/api.md |
| jonobones | v0.1.0 | `c5dacdd` | bug: run the post-sync event scan before the cycle reports complete | changes src/daemon.ts |
| jonobones | v0.1.0 | `2396941` | bug: default sync.target to none (API-only) instead of filesystem | changes src/config/defaults.ts |
| jonobones | v0.1.1 | `92e6119` | ops-ghcr-publish: publish images to ghcr.io on version tags | changes .github/workflows/release.yml |
| jonobones | v0.1.1 | `b5d785b` | ops-npm-publish: auto-publish to npm on version tags (trusted publishing) | changes .github/workflows/release.yml |
| jonobones | v0.1.1 | `ccff9ac` | ops-npm-scoped-alias: @parkviewlab/jonobones as a functional alias | changes .github/workflows/release.yml |
| jonobones | v0.1.1 | `c30fad2` | doc-northstar-html: designed HTML presentation of the northstar | changes docs/northstar.html |
| jonobones | v0.1.2 | `f4fc555` | e2e tier: real Joplin Server + official CLI + example app + SSE | changes examples/README.md |
| jonobones | v0.1.2 | `1fc8b25` | ci: e2e job — Joplin Server e2e tier on every push/PR | changes .github/workflows/ci.yml |
| jonobones | v0.1.2 | `66c7455` | docs: testing.md — the four tiers and a manual playground | changes README.md |
| jonobones | v0.1.2 | `78b8a08` | e2e: harden e2ee suite against silent CLI sync no-ops (CI flake) | changes tests/e2e/harness.ts |
| jonobones | v0.1.3 | `2179163` | docs: container quickstart in README + Joplin Server origin gotcha | changes README.md |
| jonobones | v0.1.4 | `e4be1e7` | e2e: containerized suite — the image as a user deploys it | changes tests/e2e/global-setup.ts |
| jonobones | v0.1.4 | `1fc334d` | docs: testing.md enumerates every test, step by step | changes docs/testing.md |
| jonobones | v0.1.4 | `fb779cc` | e2e: stop using `joplin e2ee enable` — it races its own settings flush | changes docs/testing.md |
| paper-boxing | v0.1.0 | `89ebea7` | chore: initial commit | root commit |
| cobalt-grinding | v0.1.0 | `dd57644` | Initial public release — cobalt-grinding (AGPL-3.0-or-later) | root commit |
| cogrind-workshop | v0.1.0 | `8208257` | Initial public release — cogrind-workshop (AGPL-3.0-or-later) | root commit |
| cogrind-workshop | v0.1.0 | `958c3f5` | ci: bump action pins to Node 24 | changes .github/workflows/release.yml |

### Bookkeeping recognised by content

| Bookkeeping reason | Commits |
|---|---|
| (i) version value only | 112 |
| (ii) CHANGELOG.md only | 40 |
| (iii) other merge, tree equals the automatic merge | 88 |
| carrier merge, tree equals the automatic merge | 21 |
| Total | 261 |

Every bookkeeping commit was recognised by what it changes, not by its title. Titles appear in the data only as a check: the 112 version-only commits are all titled as releases, open cycles, dev builds or version bumps, and the 40 changelog-only commits are all 'docs(changelog): vX [skip ci]'. Of the 109 merges examined under R5(iii), none has a tree that differs from the automatic merge of its parents, so no merge in the ten repositories carries a change of its own.

## Part three: the published side, recounted by the same scope

### Artefacts

50 of the 81 tags have a GitHub Release. 26 have only a section in CHANGELOG.md on main, 23 of which hold a Highlights paragraph and no list. 5 (jonobones v0.1.0 to v0.1.4) have neither, and none of those five contains a pull request. 36 tags have no list at all: the 23 sections just named, the 5 tags with nothing, and 8 Releases (5 first releases, plus smalt-mcp v1.3.0, ebony-enriching v0.1.5 and flint-slating v0.1.5).

| Repository | Tags | GitHub Release | CHANGELOG.md section only | Neither | Tags with no list | Expected | Published by number | Omitted | of which by hash | Noise: release-job commit | Noise: change without a pull request |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pensa-grex | 19 | 19 | 0 | 0 | 1 | 97 | 60 | 37 | 0 | 10 | 2 |
| deco-assaying | 16 | 7 | 9 | 0 | 6 | 15 | 2 | 13 | 5 | 6 | 0 |
| smalt-mcp | 12 | 4 | 8 | 0 | 9 | 30 | 1 | 29 | 0 | 3 | 0 |
| ebony-enriching | 11 | 6 | 5 | 0 | 6 | 17 | 2 | 15 | 0 | 5 | 0 |
| conception-space | 7 | 7 | 0 | 0 | 1 | 22 | 11 | 11 | 0 | 6 | 0 |
| flint-slating | 6 | 2 | 4 | 0 | 5 | 8 | 0 | 8 | 0 | 1 | 0 |
| jonobones | 6 | 1 | 0 | 5 | 5 | 3 | 1 | 2 | 0 | 0 | 0 |
| paper-boxing | 2 | 2 | 0 | 0 | 1 | 9 | 3 | 6 | 0 | 1 | 0 |
| cobalt-grinding | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| cogrind-workshop | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| Total | 81 | 50 | 26 | 5 | 36 | 202 | 80 | 122 | 5 | 32 | 2 |

"Published by number" counts expected pull requests whose number appears in a list line. Two published numbers are not expected where they appear: conception-space v0.8.2 lists #11 and #12, the cherry-picks of Part two, and v0.8.3 lists them again; under the rule the first listing is right and the second is the duplicate.

### Causes of the 122 omissions, in the prescribed order

Each omission is attributed to exactly one cause, tested in this order: the first release's empty range; a tag published with no list; the written prefix policy (a title of type build, chore, ci or style, or with no recognised type); a real merge at GitHub's default title skipped by cliff.toml's `^Merge` rule; anything else.

| Repository | First release's empty range | Tag published with no list | Written prefix policy | Default-title merge skipped by ^Merge | Other | Total |
|---|---|---|---|---|---|---|
| pensa-grex | 36 | 0 | 1 | 0 | 0 | 37 |
| deco-assaying | 0 | 0 | 12 | 1 | 0 | 13 |
| smalt-mcp | 4 | 23 | 2 | 0 | 0 | 29 |
| ebony-enriching | 6 | 6 | 3 | 0 | 0 | 15 |
| conception-space | 6 | 0 | 5 | 0 | 0 | 11 |
| flint-slating | 2 | 5 | 1 | 0 | 0 | 8 |
| jonobones | 0 | 0 | 2 | 0 | 0 | 2 |
| paper-boxing | 6 | 0 | 0 | 0 | 0 | 6 |
| cobalt-grinding | 0 | 0 | 0 | 0 | 0 | 0 |
| cogrind-workshop | 1 | 0 | 0 | 0 | 0 | 1 |
| Total | 61 | 34 | 26 | 1 | 0 | 122 |

No omission falls under "other": every one is explained by the first four causes.

The prescribed order assigns each omission to the first cause that applies, which hides overlaps. By merge method:

| Cause (prescribed order) | squash | real merge, default title | real merge, titled |
|---|---|---|---|
| first release's empty range | 49 | 12 | 0 |
| tag published with no list | 3 | 31 | 0 |
| written prefix policy | 21 | 5 | 0 |
| real merge at default title skipped by ^Merge | 0 | 1 | 0 |
| other | 0 | 0 | 0 |

Two facts qualify the order. First, "tag published with no list" is not an independent cause: re-running git-cliff over each of those ranges with the repository's own cliff.toml produces an empty list every time, because every commit in the range is dropped by the filters (31 of the 34 are default-title merges, the other 3 are ci or chore squashes). Second, the first-release omissions overlap with the filters. Counting instead every mechanism that dropped each pull request:

| Mechanisms that dropped the pull request | Omissions |
|---|---|
| empty first-release range | 42 |
| ^Merge skip | 37 |
| prefix or unrecognised type | 24 |
| empty first-release range + ^Merge skip | 12 |
| empty first-release range + prefix or unrecognised type | 7 |
| Total | 122 |

The empty first-release range alone accounts for 42 omissions; the filters account for the other 80 (the `^Merge` skip for 49 of the 122, the prefix policy for 31, counting the first-release overlaps). The first-release overlap in detail, from git-cliff re-run over `<root>..<tag>`:

| Repository | First-release omissions | Listed by git-cliff over root..tag | Still dropped by the filters |
|---|---|---|---|
| pensa-grex | 36 | 31 | #30, #31, #32, #35, #36 |
| smalt-mcp | 4 | 0 | #1, #2, #3, #4 |
| ebony-enriching | 6 | 0 | #1, #2, #3, #4, #5, #6 |
| conception-space | 6 | 5 | #3 |
| flint-slating | 2 | 0 | #1, #2 |
| paper-boxing | 6 | 6 |  |
| cogrind-workshop | 1 | 0 | #2 |
| Total | 61 | 42 |  |

### Omissions published by commit hash

5 of the 122 were published, under the hash of a commit inside the pull request rather than by number. All are deco-assaying pull requests merged at GitHub's default title, whose merge commit git-cliff skipped while it listed a conventional commit from the branch.

| Repository | Tag | PR | Published commit |
|---|---|---|---|
| deco-assaying | v0.1.6 | #1 | 9a221d9 |
| deco-assaying | v0.1.7 | #3 | 3d24dd6 |
| deco-assaying | v0.2.0 | #5 | a7de363 |
| deco-assaying | v0.2.1 | #8 | b3dd7ac |
| deco-assaying | v0.3.0 | #10 | 3ed745f |

### Noise

34 published list lines correspond to no pull request. 32 are the release job's own changelog commit, 'docs(changelog): vX [skip ci]', which lands on main after the tag it documents and is therefore listed in the next release (pensa-grex 10, deco-assaying 6, conception-space 6, ebony-enriching 5, smalt-mcp 3, flint-slating 1, paper-boxing 1). 2 are real changes made without a pull request, pensa-grex v3.1.0 d8f9d8e and baab775, which the rule lists under Direct commits. The five deco-assaying lines cited by hash are not noise: they belong to pull requests (above).

| Repository | Tag | Published line | Kind |
|---|---|---|---|
| pensa-grex | v1.0.1 | - V1.0.0 [skip ci] (20c9f61) | release-job changelog commit |
| pensa-grex | v1.0.2 | - V1.0.1 [skip ci] (942e8da) | release-job changelog commit |
| pensa-grex | v1.1.0 | - V1.0.2 [skip ci] (c0a7a51) | release-job changelog commit |
| pensa-grex | v1.2.0 | - V1.1.0 [skip ci] (e5b88c0) | release-job changelog commit |
| pensa-grex | v1.3.0 | - V1.2.0 [skip ci] (9393784) | release-job changelog commit |
| pensa-grex | v1.3.1 | - V1.3.0 [skip ci] (ff06b3b) | release-job changelog commit |
| pensa-grex | v1.3.2 | - V1.3.1 [skip ci] (c93aa86) | release-job changelog commit |
| pensa-grex | v2.0.0 | - V1.3.2 [skip ci] (4eb9028) | release-job changelog commit |
| pensa-grex | v2.1.0 | - V2.0.0 [skip ci] (7e385d6) | release-job changelog commit |
| pensa-grex | v3.0.0 | - V2.1.0 [skip ci] (8da2835) | release-job changelog commit |
| pensa-grex | v3.1.0 | - Keep a hidden card's silhouette instead of painting a zero box (d8f9d8e) | real change without a pull request |
| pensa-grex | v3.1.0 | - Say plainly that the v3 bookmark shape is only half shipped (baab775) | real change without a pull request |
| deco-assaying | v0.3.0 | - V0.2.1 [skip ci] (4c09e60) | release-job changelog commit |
| deco-assaying | v0.3.1 | - V0.3.0 [skip ci] (df816bb) | release-job changelog commit |
| deco-assaying | v0.3.2 | - V0.3.1 [skip ci] (48b508f) | release-job changelog commit |
| deco-assaying | v0.3.3 | - V0.3.2 [skip ci] (c74446f) | release-job changelog commit |
| deco-assaying | v0.3.4 | - V0.3.3 [skip ci] (c589bc5) | release-job changelog commit |
| deco-assaying | v0.3.5 | - V0.3.4 [skip ci] (4444f97) | release-job changelog commit |
| smalt-mcp | v1.3.1 | - V1.3.0 [skip ci] (8941151) | release-job changelog commit |
| smalt-mcp | v1.3.2 | - V1.3.1 [skip ci] (1bbe671) | release-job changelog commit |
| smalt-mcp | v1.3.3 | - V1.3.2 [skip ci] (3dee2ea) | release-job changelog commit |
| ebony-enriching | v0.1.6 | - V0.1.5 [skip ci] (ae1e245) | release-job changelog commit |
| ebony-enriching | v0.1.7 | - V0.1.6 [skip ci] (8378323) | release-job changelog commit |
| ebony-enriching | v0.1.8 | - V0.1.7 [skip ci] (575fc0d) | release-job changelog commit |
| ebony-enriching | v0.1.9 | - V0.1.8 [skip ci] (87f05d0) | release-job changelog commit |
| ebony-enriching | v0.1.10 | - V0.1.9 [skip ci] (d571ad6) | release-job changelog commit |
| conception-space | v0.8.1 | - V0.8.0 [skip ci] (6f55bf5) | release-job changelog commit |
| conception-space | v0.8.2 | - V0.8.1 [skip ci] (3911fb9) | release-job changelog commit |
| conception-space | v0.8.3 | - V0.8.2 [skip ci] (ac4291d) | release-job changelog commit |
| conception-space | v0.8.4 | - V0.8.3 [skip ci] (08713af) | release-job changelog commit |
| conception-space | v0.8.5 | - V0.8.4 [skip ci] (4c3e675) | release-job changelog commit |
| conception-space | v0.8.6 | - V0.8.5 [skip ci] (68fe52b) | release-job changelog commit |
| flint-slating | v0.1.6 | - V0.1.5 [skip ci] (e37d96f) | release-job changelog commit |
| paper-boxing | v0.1.1 | - V0.1.0 [skip ci] (5f1028d) | release-job changelog commit |

### Reproduction of the published lists

git-cliff 2.13.1 was run over every release range with the repository's cliff.toml as at the tag (origin/main's where the tag has none). Result: 78 of 81 identical; different: jonobones v0.1.2 (published source: none; re-run items 1); jonobones v0.1.3 (published source: none; re-run items 1); jonobones v0.1.4 (published source: none; re-run items 1). Those three tags have no published artefact; all 76 tags that have one are reproduced exactly. Every published list is therefore git-cliff's output under the repository's own configuration and range, and the omissions and the noise are properties of that generator, not of hand editing.

### Per release

| Repository | Tag | Published | List lines | Expected | Published by number | Published, not expected | Omitted | Causes | Noise lines |
|---|---|---|---|---|---|---|---|---|---|
| pensa-grex | v1.0.0 | Release | 0 | 36 | 0 |  | 36 | first 36 | 0 |
| pensa-grex | v1.0.1 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| pensa-grex | v1.0.2 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| pensa-grex | v1.1.0 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| pensa-grex | v1.2.0 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| pensa-grex | v1.3.0 | Release | 9 | 8 | 8 |  | 0 |  | 1 |
| pensa-grex | v1.3.1 | Release | 4 | 3 | 3 |  | 0 |  | 1 |
| pensa-grex | v1.3.2 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| pensa-grex | v2.0.0 | Release | 5 | 4 | 4 |  | 0 |  | 1 |
| pensa-grex | v2.1.0 | Release | 4 | 3 | 3 |  | 0 |  | 1 |
| pensa-grex | v3.0.0 | Release | 11 | 10 | 10 |  | 0 |  | 1 |
| pensa-grex | v3.1.0 | Release | 3 | 1 | 1 |  | 0 |  | 2 |
| pensa-grex | v3.2.0 | Release | 3 | 3 | 3 |  | 0 |  | 0 |
| pensa-grex | v3.2.1 | Release | 1 | 1 | 1 |  | 0 |  | 0 |
| pensa-grex | v3.2.2 | Release | 1 | 1 | 1 |  | 0 |  | 0 |
| pensa-grex | v3.3.0 | Release | 7 | 7 | 7 |  | 0 |  | 0 |
| pensa-grex | v3.4.0 | Release | 3 | 3 | 3 |  | 0 |  | 0 |
| pensa-grex | v3.5.0 | Release | 3 | 3 | 3 |  | 0 |  | 0 |
| pensa-grex | v3.5.1 | Release | 9 | 9 | 9 |  | 0 |  | 0 |
| deco-assaying | v0.1.0 | CHANGELOG.md | 0 | 0 | 0 |  | 0 |  | 0 |
| deco-assaying | v0.1.1 | CHANGELOG.md | 0 | 0 | 0 |  | 0 |  | 0 |
| deco-assaying | v0.1.2 | CHANGELOG.md | 0 | 0 | 0 |  | 0 |  | 0 |
| deco-assaying | v0.1.3 | CHANGELOG.md | 0 | 0 | 0 |  | 0 |  | 0 |
| deco-assaying | v0.1.4 | CHANGELOG.md | 0 | 0 | 0 |  | 0 |  | 0 |
| deco-assaying | v0.1.5 | CHANGELOG.md | 0 | 0 | 0 |  | 0 |  | 0 |
| deco-assaying | v0.1.6 | CHANGELOG.md | 1 | 1 | 0 |  | 1 | prefix 1 | 0 |
| deco-assaying | v0.1.7 | CHANGELOG.md | 1 | 1 | 0 |  | 1 | prefix 1 | 0 |
| deco-assaying | v0.2.0 | CHANGELOG.md | 1 | 1 | 0 |  | 1 | prefix 1 | 0 |
| deco-assaying | v0.2.1 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 0 |
| deco-assaying | v0.3.0 | Release | 2 | 3 | 0 |  | 3 | ^Merge 1, prefix 2 | 1 |
| deco-assaying | v0.3.1 | Release | 2 | 2 | 1 |  | 1 | prefix 1 | 1 |
| deco-assaying | v0.3.2 | Release | 2 | 3 | 1 |  | 2 | prefix 2 | 1 |
| deco-assaying | v0.3.3 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| deco-assaying | v0.3.4 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| deco-assaying | v0.3.5 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| smalt-mcp | v0.1.0 | CHANGELOG.md | 0 | 4 | 0 |  | 4 | first 4 | 0 |
| smalt-mcp | v0.2.0 | CHANGELOG.md | 0 | 2 | 0 |  | 2 | no list 2 | 0 |
| smalt-mcp | v0.3.0 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| smalt-mcp | v0.4.0 | CHANGELOG.md | 0 | 2 | 0 |  | 2 | no list 2 | 0 |
| smalt-mcp | v0.5.0 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| smalt-mcp | v1.0.0 | CHANGELOG.md | 0 | 13 | 0 |  | 13 | no list 13 | 0 |
| smalt-mcp | v1.1.0 | CHANGELOG.md | 0 | 2 | 0 |  | 2 | no list 2 | 0 |
| smalt-mcp | v1.2.0 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| smalt-mcp | v1.3.0 | Release | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| smalt-mcp | v1.3.1 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| smalt-mcp | v1.3.2 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| smalt-mcp | v1.3.3 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| ebony-enriching | v0.1.0 | CHANGELOG.md | 0 | 6 | 0 |  | 6 | first 6 | 0 |
| ebony-enriching | v0.1.1 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| ebony-enriching | v0.1.2 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| ebony-enriching | v0.1.3 | CHANGELOG.md | 0 | 2 | 0 |  | 2 | no list 2 | 0 |
| ebony-enriching | v0.1.4 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| ebony-enriching | v0.1.5 | Release | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| ebony-enriching | v0.1.6 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| ebony-enriching | v0.1.7 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| ebony-enriching | v0.1.8 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| ebony-enriching | v0.1.9 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| ebony-enriching | v0.1.10 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| conception-space | v0.8.0 | Release | 0 | 6 | 0 |  | 6 | first 6 | 0 |
| conception-space | v0.8.1 | Release | 2 | 1 | 1 |  | 0 |  | 1 |
| conception-space | v0.8.2 | Release | 4 | 1 | 1 | #11, #12 | 0 |  | 1 |
| conception-space | v0.8.3 | Release | 4 | 3 | 3 |  | 0 |  | 1 |
| conception-space | v0.8.4 | Release | 5 | 5 | 4 |  | 1 | prefix 1 | 1 |
| conception-space | v0.8.5 | Release | 2 | 4 | 1 |  | 3 | prefix 3 | 1 |
| conception-space | v0.8.6 | Release | 2 | 2 | 1 |  | 1 | prefix 1 | 1 |
| flint-slating | v0.1.0 | CHANGELOG.md | 0 | 2 | 0 |  | 2 | first 2 | 0 |
| flint-slating | v0.1.1 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| flint-slating | v0.1.2 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| flint-slating | v0.1.4 | CHANGELOG.md | 0 | 1 | 0 |  | 1 | no list 1 | 0 |
| flint-slating | v0.1.5 | Release | 0 | 2 | 0 |  | 2 | no list 2 | 0 |
| flint-slating | v0.1.6 | Release | 1 | 1 | 0 |  | 1 | prefix 1 | 1 |
| jonobones | v0.1.0 | none | 0 | 0 | 0 |  | 0 |  | 0 |
| jonobones | v0.1.1 | none | 0 | 0 | 0 |  | 0 |  | 0 |
| jonobones | v0.1.2 | none | 0 | 0 | 0 |  | 0 |  | 0 |
| jonobones | v0.1.3 | none | 0 | 0 | 0 |  | 0 |  | 0 |
| jonobones | v0.1.4 | none | 0 | 0 | 0 |  | 0 |  | 0 |
| jonobones | v0.1.5 | Release | 1 | 3 | 1 |  | 2 | prefix 2 | 0 |
| paper-boxing | v0.1.0 | Release | 0 | 6 | 0 |  | 6 | first 6 | 0 |
| paper-boxing | v0.1.1 | Release | 4 | 3 | 3 |  | 0 |  | 1 |
| cobalt-grinding | v0.1.0 | Release | 0 | 0 | 0 |  | 0 |  | 0 |
| cogrind-workshop | v0.1.0 | Release | 0 | 1 | 0 |  | 1 | first 1 | 0 |

### Every omission

| Repository | Tag | PR | Title (R6) | Merge | Cause | Published by hash |
|---|---|---|---|---|---|---|
| pensa-grex | v1.0.0 | #1 | feat: renderer shell and Light/Dark theme | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #2 | feat: port the static skin into renderer modules | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #3 | docs: tree-grammar study, subway forest mock, and model decisions | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #4 | feat: forest data model, validation, and a real JSON5 fixture | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #5 | feat: the layout engine — real forest data now drives the whole scene | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #6 | feat: persistence bridge, IPC, domain switcher, and legal bundle | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #7 | feat: right-click editing — statuses, cursors, add, and delete | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #8 | feat: per-task markdown note editor | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #9 | docs: project northstar, and ready the app for a first release | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #10 | feat: create domains from the switcher, and a theme-aware sputnik cursor | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #11 | fix: pre-release hardening — sanitise notes, add a CSP, and 12 more review fixes | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #12 | fix: non-crossing tidy-tree branch layout and tip-fork connector | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #13 | feat: delete a domain (move to Trash) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #14 | feat: open note editor in two-pane edit mode; View/Edit toggle | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #15 | fix: give the current task its status colour, not the in-progress colour | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #16 | feat: mid-century typography — League Spartan (UI) + Boogaloo (names) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #17 | feat: angle branch connectors upward (render-only) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #18 | fix: enlarge task names to 15px | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #19 | feat: grow branches upward along a single constant-angle ray | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #20 | feat: sub-projects data model, schema v2 migration, structural roots | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #21 | feat: googie node shapes and atomic decorators | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #22 | feat: collapse and expand project nodes (client-local view state) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #23 | feat: copy a project and paste it as a new tree across domains | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #24 | feat: export a project subtree to a markdown outline | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #25 | feat: drag-and-drop move, graft, nest, detach, and reorder | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #26 | feat: bookmarked views, shared in the domain, applied to the live view | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #27 | docs: sub-projects visual system, drag-and-drop, bookmarks, axiom 8 | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #28 | feat: reorder nodes within a line (drag into a gap, move up/down) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #29 | feat: hyphenate long node labels and widen cards to 188px | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #30 | chore: credit vendored hyphenation patterns in the licenses window | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #31 | chore: adopt ParkviewLab identity (garyf@parkviewlab.ai) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #32 | chore: rename to PensaGrex | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #33 | feat: add ParkviewLab app icon | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #34 | fix: upgrade Electron to a supported release (34 → 43) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #35 | build: upgrade Vite toolchain (vite 7, electron-vite 5, vitest 4) | squash | first release's empty range |  |
| pensa-grex | v1.0.0 | #36 | build: complete Electron prebuilt extraction before the legal step | squash | first release's empty range |  |
| pensa-grex | v1.0.2 | #38 | build: drop inert yauzl override (Electron 43 extracts via install.js) | squash | written prefix policy |  |
| deco-assaying | v0.1.6 | #1 | release flow: gate job + dev-tools helpers in README | merge-default-title | written prefix policy | 9a221d9 |
| deco-assaying | v0.1.7 | #3 | Add --transport stdio CLI flag for MCP stdio transport | merge-default-title | written prefix policy | 3d24dd6 |
| deco-assaying | v0.2.0 | #5 | Block GPL-3.0 ebnf grammar from being loaded | merge-default-title | written prefix policy | a7de363 |
| deco-assaying | v0.2.1 | #8 | ci: automated changelog + GitHub Release generation | merge-default-title | written prefix policy | b3dd7ac |
| deco-assaying | v0.3.0 | #7 | Bump idna from 3.13 to 3.15 in the uv group across 1 directory | merge-default-title | written prefix policy |  |
| deco-assaying | v0.3.0 | #10 | fix: point stale garycoding references at the ParkviewLab namespace | merge-default-title | real merge at default title skipped by ^Merge | 3ed745f |
| deco-assaying | v0.3.0 | #11 | chore: adopt ParkviewLab conventions and relicense to MIT OR Apache-2.0 | squash | written prefix policy |  |
| deco-assaying | v0.3.1 | #12 | chore: adopt latest handbook conventions (dev-release.yml + thin AI pointers) | squash | written prefix policy |  |
| deco-assaying | v0.3.2 | #14 | build(deps): bump pyjwt from 2.12.1 to 2.13.0 in the uv group across 1 directory | squash | written prefix policy |  |
| deco-assaying | v0.3.2 | #15 | build(deps): bump the uv group across 1 directory with 3 updates | squash | written prefix policy |  |
| deco-assaying | v0.3.3 | #17 | ci: bump release.yml action pins to Node 24 (checkout@v6, setup-uv@v8.1.0) | squash | written prefix policy |  |
| deco-assaying | v0.3.4 | #18 | ci: bump action pins to Node 24 | squash | written prefix policy |  |
| deco-assaying | v0.3.5 | #19 | build(deps): bump mcp from 1.27.0 to 1.28.1 in the uv group across 1 directory | squash | written prefix policy |  |
| smalt-mcp | v0.1.0 | #1 | v0 foundation: scaffold + storage port + status tool | merge-default-title | first release's empty range |  |
| smalt-mcp | v0.1.0 | #2 | tools: list_pages, read_page, traverse, search + test seed Smalt | merge-default-title | first release's empty range |  |
| smalt-mcp | v0.1.0 | #3 | v0 tool surface complete: write tools + domains + ProposalPage + 3 more tools | merge-default-title | first release's empty range |  |
| smalt-mcp | v0.1.0 | #4 | tools: add_link, add_claim — v0 surface feature-complete | merge-default-title | first release's empty range |  |
| smalt-mcp | v0.2.0 | #6 | schema+tools: ID validation + always-mangle write_page (collision-free creates) | merge-default-title | tag published with no list |  |
| smalt-mcp | v0.2.0 | #7 | tools: find_by_alias + read_page alias fallback | merge-default-title | tag published with no list |  |
| smalt-mcp | v0.3.0 | #9 | tools: incoming_links + remove_page/update_claim/remove_claim/remove_link + 3-ti | merge-default-title | tag published with no list |  |
| smalt-mcp | v0.4.0 | #11 | search: aliases per hit + /health & /admin/* OpenAPI tags | merge-default-title | tag published with no list |  |
| smalt-mcp | v0.4.0 | #12 | search: alias matching as a third retrieval source | merge-default-title | tag published with no list |  |
| smalt-mcp | v0.5.0 | #14 | cleave: drop proposal/experiment/gap surface (-> ebony-enriching) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #16 | C-1: multi-hop traverse (BFS; honors hops>1) — Cogitate M7 unblocker | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #17 | C-2: property filters on list_pages + search | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #18 | C-3: IndexPage page type + auto-regeneration | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #19 | C-4: section-page id format (M3 hybrid layout) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #20 | C-5: bulk add_links + add_claims (single-op batch) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #21 | C-6: write_batch (mixed-op atomic transaction) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #23 | C-7 REVISED: revert /admin/backup endpoint + document Restic-native pattern | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #24 | C-8: observability — /admin/health + index_status tool + surface silent FTS/ANN  | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #25 | C-9: reindex_page + reindex_all MCP tools | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #26 | C-10: aliases LanceDB column + array_has lookups (perf foundation) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #27 | C-11: fuzzy alias match (trigram-Jaccard fallback) — v0.16.0 | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #28 | C-12: source_similarity MCP tool (vector-search by stored embedding) — v0.17.0 | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.0.0 | #29 | C-13: async task model — v1.0.0 (BIG) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.1.0 | #31 | E-1: init locks + obs lock + eager init (v1.0.1 patch) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.1.0 | #32 | E-2 + E-3: wrap every handler in asyncio.to_thread (v1.1.0) | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.2.0 | #34 | Add stdio MCP transport via --transport flag | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.3.0 | #38 | ci: automated changelog + GitHub Release generation | merge-default-title | tag published with no list |  |
| smalt-mcp | v1.3.1 | #42 | chore: adopt handbook conventions + uniform MIT OR Apache-2.0 license | squash | written prefix policy |  |
| smalt-mcp | v1.3.3 | #44 | ci: bump action pins to Node 24 | squash | written prefix policy |  |
| ebony-enriching | v0.1.0 | #1 | B-1 + B-2: scaffold + schema + bootstrap (ebony-enriching v0.1) | merge-default-title | first release's empty range |  |
| ebony-enriching | v0.1.0 | #2 | B-3: proposal CRUD | merge-default-title | first release's empty range |  |
| ebony-enriching | v0.1.0 | #3 | B-4: experiments (write / read / list) | merge-default-title | first release's empty range |  |
| ebony-enriching | v0.1.0 | #4 | B-5: gaps + full v0.1 tool surface | merge-default-title | first release's empty range |  |
| ebony-enriching | v0.1.0 | #5 | B-6: cross-substrate scenario tests | merge-default-title | first release's empty range |  |
| ebony-enriching | v0.1.0 | #6 | B-7: README polish — lab-notebook framing + operating modes | merge-default-title | first release's empty range |  |
| ebony-enriching | v0.1.1 | #8 | B-9: fix three v0.1.0 critical findings (C1 / C2 / C3) — v0.1.1 | merge-default-title | tag published with no list |  |
| ebony-enriching | v0.1.2 | #10 | B-10: fix 7 should-fix findings + secondary write bug — v0.1.2 | merge-default-title | tag published with no list |  |
| ebony-enriching | v0.1.3 | #12 | B-11: v0.1.3 polish (deferred reviewer items) | merge-default-title | tag published with no list |  |
| ebony-enriching | v0.1.3 | #13 | B-12: strip references to other ParkviewLab projects; park cross-server test | merge-default-title | tag published with no list |  |
| ebony-enriching | v0.1.4 | #15 | B-13: true parallel handling of overlapping MCP tool requests | merge-default-title | tag published with no list |  |
| ebony-enriching | v0.1.5 | #17 | ci: automated changelog + GitHub Release generation on tag push | squash | tag published with no list |  |
| ebony-enriching | v0.1.6 | #18 | chore: adopt handbook conventions + relicense to MIT OR Apache-2.0 | squash | written prefix policy |  |
| ebony-enriching | v0.1.9 | #21 | ci: bump release.yml action pins to Node 24 (checkout@v6, setup-uv@v8.1.0) | squash | written prefix policy |  |
| ebony-enriching | v0.1.10 | #22 | ci: bump action pins to Node 24 | squash | written prefix policy |  |
| conception-space | v0.8.0 | #2 | refactor: become a pure Electron app at repo root | squash | first release's empty range |  |
| conception-space | v0.8.0 | #3 | chore: onboard to ParkviewLab conventions (CI, AGENTS/CLAUDE, changelog, ESLint) | squash | first release's empty range |  |
| conception-space | v0.8.0 | #4 | feat: cross-platform Electron release CI (electron-builder, macOS/Windows/Linux) | squash | first release's empty range |  |
| conception-space | v0.8.0 | #5 | feat: add app icon (B&W ParkviewLab mark) | squash | first release's empty range |  |
| conception-space | v0.8.0 | #6 | docs: rework northstar (hard-edge HTML) + SPDX headers + HTML copyright footers | squash | first release's empty range |  |
| conception-space | v0.8.0 | #7 | docs: front-door polish for public launch | squash | first release's empty range |  |
| conception-space | v0.8.4 | #19 | ci: bump action pins to Node 24 | squash | written prefix policy |  |
| conception-space | v0.8.5 | #21 | build: upgrade electron-vite 2 → 5 and vite 5 → 7 | squash | written prefix policy |  |
| conception-space | v0.8.5 | #22 | build: clear residual npm advisories (undici, @babel/core) | squash | written prefix policy |  |
| conception-space | v0.8.5 | #23 | ci: complete Electron prebuilt extraction before npm run legal | squash | written prefix policy |  |
| conception-space | v0.8.6 | #24 | build: correct electron-43 extraction rationale, drop inert yauzl override | squash | written prefix policy |  |
| flint-slating | v0.1.0 | #1 | feat: PDF-reading MCP server (v0) | merge-default-title | first release's empty range |  |
| flint-slating | v0.1.0 | #2 | refactor: --transport {http,stdio} CLI (matches deco-assaying) | merge-default-title | first release's empty range |  |
| flint-slating | v0.1.1 | #3 | Dockerfile: drop Docling model pre-fetch (release v0.1.1) | merge-default-title | tag published with no list |  |
| flint-slating | v0.1.2 | #4 | ci: bump action versions to the Node 24 line | merge-default-title | tag published with no list |  |
| flint-slating | v0.1.4 | #5 | License hygiene: drop NVIDIA libs + add THIRD_PARTY_LICENSES.md | merge-default-title | tag published with no list |  |
| flint-slating | v0.1.5 | #6 | ci: automated changelog + GitHub Release generation on tag push | squash | tag published with no list |  |
| flint-slating | v0.1.5 | #7 | chore: onboard to handbook conventions + relicense to MIT OR Apache-2.0 | squash | tag published with no list |  |
| flint-slating | v0.1.6 | #8 | ci: bump action pins to Node 24 | squash | written prefix policy |  |
| jonobones | v0.1.5 | #1 | chore: onboard to handbook conventions (REUSE/AGPL, AGENTS/CLAUDE, CI, changelog | squash | written prefix policy |  |
| jonobones | v0.1.5 | #3 | ci: bump action pins to Node 24 | squash | written prefix policy |  |
| paper-boxing | v0.1.0 | #1 | feat: scaffold the package, API contract, images, workflows and docs | squash | first release's empty range |  |
| paper-boxing | v0.1.0 | #2 | feat: backend storage, accounts, tokens and the REST API | squash | first release's empty range |  |
| paper-boxing | v0.1.0 | #3 | feat: MCP server tools with per-request token confirmation | squash | first release's empty range |  |
| paper-boxing | v0.1.0 | #4 | feat: NiceGUI frontend with sign-in, sites, files, tokens, users and account pag | squash | first release's empty range |  |
| paper-boxing | v0.1.0 | #5 | feat(frontend): the ParkviewLab logo in the frame | squash | first release's empty range |  |
| paper-boxing | v0.1.0 | #6 | docs: complete the deployment guide and prove it with the integration tier | squash | first release's empty range |  |
| cogrind-workshop | v0.1.0 | #2 | chore: adopt ParkviewLab handbook onboarding (CI, AI pointers, ty, .python-versi | squash | first release's empty range |  |

### Was the Highlights paragraph more accurate than the list?

There is a basis in the data for a narrower claim: the paragraph was more complete than the list in the releases where the list lost pull requests, and in a sample its specific claims are all traceable to the release's commits. There is no basis for calling it a more accurate record, because it is not a record of pull requests at all.

The mechanism is in scripts/generate_changelog.py, identical in this respect at every tag that carries it and on main. The Highlights paragraph is written by a model from `git log prev..tag` (`git log tag` for a first release), subjects and bodies, capped at 50,000 characters, with instructions to write two to four sentences and not to invent features. The list is git-cliff over `prev..tag` (`..tag` for a first release) with the prefix and `^Merge` filters. The paragraph's input is therefore immune to both mechanical losses: the empty first-release range and the filters. It has its own two limits. It is a summary of at most four sentences, and none of the 76 paragraphs cites a pull-request number. Its input is truncated: smalt-mcp v1.0.0's log is 55,580 characters, the text of C-1 (#16) begins at character 52,076, beyond the cap, and #16 is the one pull request of that release the paragraph does not describe.

The sample check was made as follows. Eight releases were chosen in which the list omitted pull requests and a Highlights paragraph exists, weighted towards the largest losses (70 omitted pull requests in all). For each omitted pull request I read the paragraph and judged whether it states the pull request's principal change; two judgements are loose (pensa-grex #16, "mid-century typography", against "mid-century Googie styling"; #20, the sub-projects data model, against "collapsible project sub-trees"). Separately, 78 specific terms from the eight paragraphs (tool names, ports, counts, library names, platform claims) were searched for in the release's commit log; every one was found, four of them only in a different wording ("12 RO + 11 RW + 4 RD" for "12 read-only, 11 read-write, 4 remove-destructive"; "6 READ_ONLY + 7 READ_WRITE"; "nginx's listing where there is none" for "directory listings"; "failed on all three OS" for "all three platforms").

| Repository | Tag | Omitted from the list | Described in Highlights | of which loosely | Not described | Claim terms checked (all found in the log) |
|---|---|---|---|---|---|---|
| pensa-grex | v1.0.0 | 36 | 18 | 2 | #2, #3, #9, #11, #12, #15, #17, #18, #19, #27, #29, #30, #31, #32, #33, #34, #35, #36 | 15 |
| smalt-mcp | v1.0.0 | 13 | 12 | 0 | #16 | 15 |
| ebony-enriching | v0.1.0 | 6 | 5 | 0 | #5 | 11 |
| paper-boxing | v0.1.0 | 6 | 5 | 0 | #5 | 11 |
| conception-space | v0.8.5 | 3 | 3 | 0 |  | 6 |
| deco-assaying | v0.3.2 | 2 | 2 | 0 |  | 6 |
| flint-slating | v0.1.5 | 2 | 2 | 0 |  | 6 |
| smalt-mcp | v0.2.0 | 2 | 2 | 0 |  | 8 |
| Total |  | 70 | 49 | 2 |  | 78 |

The paragraphs describe 49 of the 70 omitted pull requests. What they leave out is mostly maintenance and small fixes (pensa-grex's rename, identity, icon, Electron and Vite upgrades, label and connector adjustments), which is what a four-sentence summary drops by design. The check establishes traceability to the log, not correctness of the software, and eight releases are a sample, not a census.

## Part four: real merges as well as squash

In the ten repositories GitHub made 159 squash commits and 71 real merges, and every one of the 71 carries GitHub's default title; the titled merge the proposal adopts ('<title> (#N)') occurs nowhere in the measured history. The synthetic repositories below supply it.

### Main scenario

A local repository with no remote (synthetic/main-scenario), built by build_synthetic.py with fixed dates, so its hashes are reproducible. GitHub-made commits use `GIT_COMMITTER_NAME=GitHub` and `GIT_COMMITTER_EMAIL=noreply@github.com`; the release job's changelog commit uses github-actions[bot]. The matching pull-request JSON is synthetic/main-scenario.prs.json.

```
* 6463605 Dev Person | release v0.2.0 (HEAD -> main, tag: v0.2.0)
*   428a7ac Dev Person | Release: develop → main for v0.2.0
|\  
| * e559bd4 Dev Person | build: cap requests below 3 (develop)
| * e29e531 GitHub | feat!: rename the greeting API (#7)
| *   ff2fb67 GitHub | Merge pull request #5 from example/fix-typo
| |\  
| | * c7e80c4 Dev Person | correct the greeting typo (fix-typo)
| |/  
| * b8497f5 Dev Person | chore: open 0.1.1.dev0 dev cycle
| *   b6d27d1 GitHub | Merge pull request #8 from example/main
| |\  
| |/  
|/|   
* | c0f682d github-actions[bot] | docs(changelog): v0.1.0 [skip ci]
* | 00c8e50 Dev Person | release v0.1.0 (tag: v0.1.0)
* | c18fba5 Dev Person | fix: survive unicode names (#6)
* |   f76ad5a Dev Person | Release: develop → main for v0.1.0
|\ \  
| | * 8c55897 GitHub | fix: survive unicode names (#6)
| |/  
| *   00c69f2 GitHub | feat: report command (#3)
| |\  
| | * 26bb01d Dev Person | report: tests (feature/report)
| | * 0cece7f Dev Person | report: JSON output
| | *   b346ecb Dev Person | Merge branch 'develop' into feature/report
| | |\  
| | |/  
| |/|   
| * | aaa4df1 GitHub | docs: usage guide (#4)
| | * 1c799b4 Dev Person | report: skeleton
| |/  
| * b745466 GitHub | feat: greet by name (#2)
| * f0303c7 GitHub | chore: scaffold the project (#1)
|/  
* 9165031 Dev Person | docs: start the changelog
```

The history contains every case asked for: squash commits (#1, #2, #4, #6, #7); a real merge titled with its pull request's title and number (#3, 00c69f2) whose branch has three commits and one merge of develop into the branch, one branch commit carrying a `BREAKING CHANGE:` footer; a merge at GitHub's default title (#5, ff2fb67); two local release-promotion merges; a back-merge (#8, made through a pull request from main, so that R3 is exercised as well); two release bumps touching pyproject.toml and uv.lock; two changelog-only commits (the root, and the release job's commit after v0.1.0); an open-cycle bump; a cherry-pick of squash commit 8c55897 (#6) onto main before v0.1.0, with no trailer; and one direct commit, which is a dependency pin in pyproject.toml and uv.lock, so that it also tests that a change to the version files which is not a version change is listed.

What the rule should list was stated in advance in build_synthetic.py; both tags match it exactly.

v0.1.0, first release (`git rev-list v0.1.0`). Truth #1 to #4; the rule also lists #6, by patch-id, because its cherry-pick c18fba5 is in the range while its merge commit is not. #3 absorbs its four own commits (1c799b4, b346ecb, 0cece7f, 26bb01d) and is breaking through the footer in 0cece7f.

```
### Breaking changes

- Report command (#3)

### Features

- Greet by name (#2)

### Bug fixes

- Survive unicode names (#6)

### Docs

- Usage guide (#4)

### Maintenance

- Scaffold the project (#1)
```

v0.2.0 (`v0.1.0..v0.2.0`). Truth #5 to #8; #8 is a carrier and is not listed; #6's original squash commit is in the range and R4 keeps it out, because its cherry-pick is reachable from v0.1.0. #5's title comes from the pull request, since its merge has GitHub's default title. The dependency pin is the one direct commit.

```
### Breaking changes

- Rename the greeting API (#7)

### Bug fixes

- Correct the greeting typo (#5)

### Direct commits

- build: cap requests below 3 (e559bd4)
```

Bookkeeping recognised in the two releases:

- v0.1.0: `9165031` docs: start the changelog (changelog-only); `f76ad5a` Release: develop → main for v0.1.0 (merge); `00c8e50` release v0.1.0 (version-only)
- v0.2.0: `c0f682d` docs(changelog): v0.1.0 [skip ci] (changelog-only); `b6d27d1` Merge pull request #8 from example/main (carrier #8 merge); `b8497f5` chore: open 0.1.1.dev0 dev cycle (version-only); `428a7ac` Release: develop → main for v0.2.0 (merge); `6463605` release v0.2.0 (version-only)

### Supplementary scenario

A second repository (synthetic/extra-scenario) holds the cases the rule must report or cannot see. It is not part of the stated check.

```
* 2e1a4eb Dev Person | release v1.1.0 (HEAD -> main, tag: v1.1.0)
*   921036b Dev Person | Promote develop for v1.1.0
|\  
| * b20685a Dev Person | fix: tidy g (#99) (develop)
| *   8db02c7 Dev Person | Merge branch 'side' into develop
| |\  
| | * de0d467 Dev Person | side: add f (side)
| |/  
| *   60ba1d0 GitHub | feat: exporter (#3)
| |\  
| | * 7fbe2f1 Dev Person | exporter: wiring (exporter)
| | * d533ef6 Dev Person | exporter: module
| |/  
| *   9a5018a GitHub | fix: parser edge cases (#2)
| |\  
| | * 06b4417 Dev Person | parser: second edge case (parser)
| | * 1eb6d48 Dev Person | parser: first edge case
| |/  
* | b95f9be Dev Person | release v1.0.0 (tag: v1.0.0)
* | 3640ecc Dev Person | exporter: wiring
* | a20d966 Dev Person | exporter: module
* | c5aafd9 Dev Person | fix: parser edge cases (#2)
* | 9c2f43f Dev Person | Promote develop for v1.0.0
|\| 
| * 52cc19c GitHub | chore: scaffold (#1)
|/  
* fc63a76 Dev Person | docs: start the changelog
```

v1.0.0 is cut from main after picking #2's real merge with `git cherry-pick -m 1` and #3's two branch commits one by one. The rule recognises the first (patch-id of `git diff M^1 M`) and lists #2; it does not recognise the second, and lists the two picks as direct commits (D8):

```
### Bug fixes

- Parser edge cases (#2)

### Maintenance

- Scaffold (#1)

### Direct commits

- exporter: module (a20d966)
- exporter: wiring (3640ecc)
```

v1.1.0 promotes develop. #2 is not listed again (R4); #3 is listed, a second time in substance. The local merge 8db02c7, in which an extra edit was made to src/b.py, is listed as a direct commit with the warning "differs from the automatic merge: src/b.py | 2 +-", and the commit 'fix: tidy g (#99)', which GitHub did not make, is listed as a direct commit with a warning that its suffix is not believed:

```
### Features

- Exporter (#3)

### Direct commits

- side: add f (de0d467)
- Merge branch 'side' into develop (8db02c7)
- fix: tidy g (#99) (b20685a)
```

## Corrections to the earlier figures

- Proposed rule against the truth: the earlier '80 of 81 exact' described the first prototype. The rule as designed lists exactly the expected pull requests (truth less carriers) in 79 of 81 releases; the other two, conception-space v0.8.2 (#11 and #12 listed as cherry-picks) and v0.8.3 (#11 and #12 not listed again), are correct behaviour. No release has an unexplained difference.
- Carriers: 22 merged pull requests, not 21. Besides the 21 release-promotion and back-merge pull requests, R3's 'base branch is main' clause catches cogrind-workshop #1, a feature pull request into main (D9).
- Truth: 224 merged pull requests have their merge commit in a release range; expected (less carriers) 202.
- Published omissions: 122 expected pull requests are not published by number, not 144; the difference is the 22 carriers. 5 of the 122 (deco-assaying #1, #3, #5, #8, #10) were published by commit hash.
- Causes, in the prescribed order: first release's empty range 61 (not 62: the 62nd was cogrind-workshop #1, now a carrier), tag published with no list 34, written prefix policy 26, default-title merge skipped by ^Merge 1, other 0.
- The 34 'no list' omissions all fall in tags whose list git-cliff empties with the repository's own configuration: 31 are default-title merges and 3 are ci or chore squashes. Counted by mechanism rather than in the prescribed order, the ^Merge skip drops 49 of the 122, the prefix policy 31, and the empty first-release range 61, of which 42 would have been listed with a correct range.
- Noise: 34 published list lines correspond to no pull request, not 39: 32 are the release job's own changelog commits and 2 are real changes made without a pull request (pensa-grex v3.1.0 d8f9d8e and baab775). The other 5 of the earlier 39 are deco-assaying pull-request commits cited by hash.
- Direct commits: 72 commits under the content rule, not 20 (mixed units) or 65 (second prototype, title regex). The 7 added are deco-assaying c260845 and f6d34ee, the root commits of jonobones, smalt-mcp, ebony-enriching and flint-slating (the regex skipped 'Initial commit'), and cogrind-workshop 958c3f5 (D9).
- Published artefacts: 50 of 81 tags have a GitHub Release; 26 fall back to a CHANGELOG.md section on main (23 of them with no list); 5 (jonobones v0.1.0 to v0.1.4) have neither and contain no pull request.

## Files

All under /private/tmp/claude-501/-Users-gary-dev/e994abf8-7c35-4038-ac9d-b7e6b855627e/scratchpad/revise:

- proposed_list2.py: the rule.
- measure2.py: Parts two and three over the 81 releases (writes raw_measure.json).
- cliff_rerun.py: the git-cliff re-run (adds to raw_measure.json).
- build_synthetic.py: Part four (writes synthetic/, synthetic/results.json).
- report.py and decisions.py: evidence2.json and this file, from measure_template.md.
- evidence2.json: every figure above, per release and per repository.
- clones/, data/: the clones and the GitHub data used.
