# The acceptance run of `generate-changelog`

`acceptance.py` runs `scripts/generate-changelog` over every release of the ten repositories on which the rule was measured (the measurement's report is `evidence/measure.md`), and compares each list with the measurement's recorded result or, for a release made after the measurement, with the expected set that GitHub's record gives. It needs the network and `gh` logged in to GitHub, so it is not a unit test and CI does not run it; nothing here is named `test*.py` and the folder has no `__init__.py`, so `unittest` discovery never enters it. It never calls the model: the script runs without `ANTHROPIC_API_KEY`, every Highlights paragraph is the placeholder, and what is compared is the list.

The [dev-tools README](../../README.md#tests) states when the full run is made and what its differences from the recording must be. A ruled change is a difference from the recording that a ruling on the rule made. The ruling must be recorded, with its date, content and reason, under "Decided" below, and entered in `RULED` in `acceptance.py` with the list the rule now gives and one line naming the ruling. Any other difference fails the run: it is a defect to fix, or a change of the rule that needs a ruling before the release.

## Running it

From the root of the dev-tools checkout whose script is to be checked:

```bash
uv run --python 3.13 --no-project python tests/acceptance/acceptance.py full --work /tmp/gc-acceptance
uv run --python 3.13 --no-project python tests/acceptance/acceptance.py tag --clone /tmp/paper-boxing --tag v0.4.0
uv run --python 3.13 --no-project python tests/acceptance/acceptance.py release-check --clone /tmp/paper-boxing --tag v0.4.0 --report /tmp/release-check.md
```

- `full` clones the ten repositories into `--work` (a clone already there is fetched instead), runs the script's generate mode for every `vX.Y.Z` tag, and writes a report, by default `acceptance-report.md` in `--work`. It exits 0 when every tag passes and every recorded tag exists; 1 when a tag's list differs from its basis, the script fails on a tag or a recorded tag is missing; and 2 on bad arguments or when the run cannot go on (for instance gh not on PATH, or a clone, a fetch or a read from GitHub failing), in which case it writes no report, and a report from an earlier run stays as it was. A run takes about two minutes.
- `tag` makes the same comparison for one tag of one clone and prints PASS or the differences; `--report` also writes them to a file. It is a dry run: it shows the list that the script of this checkout gives for that tag, and publishes nothing.
- `release-check` is for a published tag: that comparison; the list, the pull requests and the Highlights paragraph of the tag's GitHub Release, with each published line classed as a pull request of the expected set, a direct commit or a bookkeeping commit; the tag's section of `CHANGELOG.md` on `main`, counted and compared with the Release; and the release run's jobs in the order they ran, its attempt, and the job summary the script printed into the changelog job's log. It writes all of it to `--report`, from which a reader judges the release's notes by five criteria: the list equals the expected set, each pull request under its type's group and every direct commit of the range under Direct commits; no published line is a bookkeeping commit; the Highlights paragraph is present and is not the placeholder; `CHANGELOG.md` on `main` holds the tag's section once, and the job summary names the pinned dev-tools version; and the changelog job started after every other job of the run had completed, and succeeded on the run's first attempt.

The clone given to `tag` or `release-check` must be a disposable full clone: the script writes `release-body.md` at the clone's root, and `release-check` fetches the clone first, since the release job commits to `main` after the tag.

## What it compares

- A tag the measurement recorded: the list must equal the recorded list, the `section` of that tag in `evidence/evidence2.json` (`part2.per_release`), character for character.
- A ruled difference: `RULED` in `acceptance.py` holds the list as the rule now gives it and the ruling that changed it, with the ruling's date. There is one, cogrind-workshop v0.1.0: the measurement also counted any pull request into `main` as a carrier, whereas the rule recognises a carrier by its head branch alone (D9 in the script's docstring; ruling 9a of 2026-09-18, under Decided), so #1 (from `ci-node24-action-pins` into `main`) is listed under Maintenance and its commit 958c3f5 leaves Direct commits. The rulings of the same date on two further points change the rule but no recorded list, since the measured history holds no instance of either: a pull request merged for real counts as already shipped once each of its own commits has a patch-id among the commits reachable from the previous tag (D8; ruling 9b), and a commit that changes nothing is bookkeeping rather than a direct commit (D14; ruling 9d).
- A tag released after the measurement (paper-boxing v0.2.0 onward): the pull requests listed must equal the expected set. It is computed by the measurement's method, from GitHub's record rather than from the script, but with the carriers as ruling 9a defines them: the merged pull requests whose merge commit lies in the release's range, less the pull requests from the repository itself whose head branch is `develop`, `main` or `back-merge-vX.Y.Z`.

## The evidence

`evidence/` holds the thirteen evidence files of the proposal "One changelog generator", unchanged, as they were served with it on 2026-09-18. `evidence2.json` is the fixture, and the measurement's other files record how its figures were made; `inventory.md` and `flow.md` are not the measurement's, and the table says what each is.

| File | What |
|---|---|
| `proposed_list2.py` | the rule as the measurement implemented it, its implementation choices marked DECISION in its comments and docstrings (the eighteen decided points, D1 to D18, are listed in `decisions.py` and `measure.md`); it predates the rulings 9a, 9b and 9d of 2026-09-18 (D9, D8 and D14; see Decided), on which the script's rule differs from it |
| `measure2.py` | the measurement over the 81 releases, which writes `raw_measure.json` |
| `cliff_rerun.py` | the re-run of git-cliff over every range |
| `raw_measure.json` | the measurement's raw results, per release |
| `build_synthetic.py` | the two synthetic histories and what was stated in advance for them; `tests/test_generate_changelog.py` rebuilds both |
| `report.py`, `decisions.py` | produce `evidence2.json` and `measure.md` |
| `evidence2.json` | every figure of the measurement and the recount, per release and per repository |
| `measure.md` | the measurement's own report |
| `cliff_nomerge.py`, `cliff_nomerge.json` | the git-cliff re-run with the `^Merge` rule removed |
| `inventory.md` | every line in thirteen repositories (the handbook, dev-tools, pensa-forma and the ten measured) that the proposal (A) or its companion, "Real merges and the back-merge pull request" (B), must or may change, marked A, B or A+B; made for splitting the earlier combined proposal in two |
| `flow.md` | the report on repository settings, branch protection and the release flow in the same thirteen repositories, made for the companion proposal; the proposal draws its section on settings and history from it |

The scripts ran against clones and data folders that are not kept here, so they are records, not tools to run again.

## Decided

The rulings on the rule that this run relies on, made on the decisions of the proposal "One changelog generator":

- 2026-09-18, ruling 9a (point D9 of the script's rule): a carrier is recognised by its head branch alone (`develop`, `main` or `back-merge-vX.Y.Z`), and only from the repository itself, not a fork. The measured clause "base branch is `main`" misfiled cogrind-workshop #1, a real change, as a carrier and its commit as a direct commit (`evidence/measure.md`, D9). Every other carrier in the history has head `develop` or `main`, and a fork's branch may be named `main`.
- 2026-09-18, ruling 9b (D8): a pull request merged for real and picked onto the release line commit by commit counts as shipped once each of its own commits has a patch-id among the commits reachable from the previous tag. It is then not listed again when its merge ships, and the script needs no change if pull requests are merged for real.
- 2026-09-18, ruling 9d (D14): a commit that changes nothing is bookkeeping, left out of the notes and reported in the job summary, since it is no change a reader of the notes can use.
