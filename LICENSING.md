<!--
SPDX-FileCopyrightText: 2026 Gary Frattarola <garyf@parkviewlab.ai>
SPDX-License-Identifier: CC-BY-4.0
-->

# Licensing

Copyright © 2026 **Gary Frattarola**. `dev-tools` is ParkviewLab's shared
developer tooling; it follows the org's licensing conventions (see the
[handbook's `licensing.md`](https://github.com/ParkviewLab/handbook/blob/main/docs/licensing.md)).

## Per-bucket licensing

| Bucket | License | What |
|---|---|---|
| Scripts, installer & CI — `scripts/**`, `install.sh`, `.github/**` | `AGPL-3.0-or-later` | the tooling |
| Docs & repo meta — `README.md`, this file, `AGENTS.md`, `CLAUDE.md`, `VERSION.txt` | `CC-BY-4.0` | the writing |

The split is encoded in [`REUSE.toml`](REUSE.toml) and per-file SPDX headers; the
root [`LICENSE`](LICENSE) holds the primary (AGPL-3.0-or-later) text for GitHub
detection; full license texts are in [`LICENSES/`](LICENSES/).

A commercial license for the AGPL-covered material is available — inquiries to
**garyf@parkviewlab.ai**.

## REUSE

This repo is [REUSE](https://reuse.software/)-compliant; verify with:

```bash
uvx --from "reuse[charset-normalizer]" reuse lint
```
