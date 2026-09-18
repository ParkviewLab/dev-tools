# The acceptance run of `generate-changelog`

`acceptance.py` runs `scripts/generate-changelog` over every release of the ten repositories that the proposal "One changelog generator" measured, and compares each list with the measurement's recorded result. It needs the network and `gh` logged in to GitHub, so it is not a unit test and CI does not run it; nothing here is named `test*.py` and the folder has no `__init__.py`, so `unittest` discovery never enters it. It never calls the model: the script runs without `ANTHROPIC_API_KEY`, every Highlights paragraph is the placeholder, and what is compared is the list.

The full run is made at the commit being tagged before every dev-tools release that changes the script. Each of its differences from the recording must be a ruled change.

## Running it

From the root of the dev-tools checkout whose script is to be checked:

```bash
uv run --python 3.13 --no-project python tests/acceptance/acceptance.py full --work /tmp/gc-acceptance
uv run --python 3.13 --no-project python tests/acceptance/acceptance.py tag --clone /tmp/paper-boxing --tag v0.4.0
uv run --python 3.13 --no-project python tests/acceptance/acceptance.py release-check --clone /tmp/paper-boxing --tag v0.4.0 --report /tmp/release-check.md
```

- `full` clones the ten repositories into `--work` (a clone already there is fetched instead), runs the script's generate mode for every `vX.Y.Z` tag, and writes a report, by default `acceptance-report.md` in `--work`. It exits 0 when every tag passes and every recorded tag exists, 1 otherwise; about two minutes.
- `tag` makes the same comparison for one tag of one clone and prints PASS or the differences; `--report` also writes them to a file. It is the dry run of a repository's switch.
- `release-check` is for a published tag: that comparison; the list, the pull requests and the Highlights paragraph of the tag's GitHub Release, with each published line classed as a pull request of the expected set, a direct commit or a bookkeeping commit; the tag's section of `CHANGELOG.md` on `main`, counted and compared with the Release; and the release run's jobs in the order they ran, its attempt, and the job summary the script printed into the changelog job's log. It writes all of it to `--report`, for a reader to judge the pilot's criteria against.

The clone given to `tag` or `release-check` must be a disposable full clone: the script writes `release-body.md` at the clone's root, and `release-check` fetches the clone first, since the release job commits to `main` after the tag.

## What it compares

- A tag the measurement recorded: the list must equal the recorded list, the `section` of that tag in `evidence/evidence2.json` (`part2.per_release`), character for character.
- A ruled difference: `RULED` in `acceptance.py` holds the list as the rule now gives it and the ruling that changed it. There is one, cogrind-workshop v0.1.0: under decision 9a, #1 (from `ci-node24-action-pins` into `main`) is no longer a carrier, so it is listed under Maintenance and its commit 958c3f5 leaves Direct commits. Rulings 9b and 9d change no recorded list, since the measured history holds no real merge picked commit by commit and no commit that changes nothing.
- A tag released after the measurement (paper-boxing v0.2.0 onward): the pull requests listed must equal the expected set, computed as the measurement computed it, from GitHub's record rather than from the script: the merged pull requests whose merge commit lies in the release's range, less the carriers (head branch `develop`, `main` or `back-merge-vX.Y.Z`, from the repository itself).

## The evidence

`evidence/` holds the measurement's thirteen files, unchanged, as they were served with the proposal on 2026-09-18. `evidence2.json` is the fixture; the rest is the record of how its figures were made.

| File | What |
|---|---|
| `proposed_list2.py` | the rule as the measurement implemented it, each decided point marked in its comments; before rulings 9a, 9b and 9d |
| `measure2.py` | the measurement over the 81 releases, which writes `raw_measure.json` |
| `cliff_rerun.py` | the re-run of git-cliff over every range |
| `raw_measure.json` | the measurement's raw results, per release |
| `build_synthetic.py` | the two synthetic histories and what was stated in advance for them; `tests/test_generate_changelog.py` rebuilds both |
| `report.py`, `decisions.py` | produce `evidence2.json` and `measure.md` |
| `evidence2.json` | every figure of the measurement and the recount, per release and per repository |
| `measure.md` | the measurement's own report |
| `cliff_nomerge.py`, `cliff_nomerge.json` | the git-cliff re-run with the `^Merge` rule removed |
| `inventory.md` | every affected line in the thirteen repositories |
| `flow.md` | the report on settings, protection and the release flow |

The scripts ran against clones and data folders that are not kept here, so they are records, not tools to run again.
