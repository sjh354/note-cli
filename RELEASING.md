# Releasing

Publishing runs on a `v*` tag via `.github/workflows/release.yml`, using PyPI
**Trusted Publishing** — there is no API token to create, store or rotate.

## Three names, deliberately

| | Name |
|---|---|
| PyPI distribution | `notegraph` |
| GitHub repo | `note-cli` |
| The command you type | `note` |
| The import package | `note_cli` |

PyPI rejected `note-cli` as too similar to the existing `notecli`. Only the
distribution name moved. This matters on the trusted-publisher form, where
"PyPI project name" and "Repository name" sit in adjacent fields and want
different values.

## Setup — done

Recorded here so it can be checked or rebuilt, not repeated.

| Field | Value |
|---|---|
| PyPI project name | `notegraph` |
| Owner | `sjh354` |
| Repository name | `note-cli` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

The `pypi` GitHub environment exists (created 2026-09-18). To confirm both
halves are still in place:

    gh api repos/sjh354/note-cli/environments --jq '.environments[].name'
    # expects: pypi

The PyPI half is only visible at
<https://pypi.org/manage/account/publishing/> — there is no API for it.

## Each release

**Steps 1–2 are the ones that go wrong.** A version can be uploaded to PyPI
exactly once; deleting a release does **not** free the number. A tag that
disagrees with `pyproject.toml` therefore burns a version and publishes the
wrong one, silently.

1. Move the unreleased section of `CHANGELOG.md` under the new version with
   today's date.
2. Bump `version` in `pyproject.toml` **to the same number the tag will use.**
   Confirm they agree before pushing:

       grep '^version' pyproject.toml          # -> version = "0.3.0"
       # the tag must then be exactly v0.3.0

3. Run what CI runs, locally:

       for m in store graph goal render; do python -m note_cli.$m; done
       python -m note_cli._concurrency_check
       python -m note_cli._cli_check

4. Confirm `SKILL.md` is inside the wheel. **CI does not check this** — its
   build job runs `twine check`, which validates metadata, not contents. A
   missing `SKILL.md` breaks `note skill --install` for every user without
   failing a single test:

       python -m build
       python -m twine check dist/*
       python -m zipfile -l dist/*.whl | grep SKILL.md

5. Commit, tag, push. The tag is what triggers publishing, so push `main`
   first — otherwise the workflow builds a commit nobody else can see:

       git commit -am "release: 0.3.0"
       git push origin main
       git tag -a v0.3.0 -m "notegraph 0.3.0"
       git push origin v0.3.0

6. Watch it, and check the result:

       gh run watch --repo sjh354/note-cli
       pip download notegraph==0.3.0 --no-deps -d /tmp/verify

## The first release

`0.2.0` is bumped and unreleased. Steps 1 and 2 are already done for it —
`pyproject.toml` says `0.2.0` and `CHANGELOG.md` has a `0.2.0` section that
needs its date. Start at step 3, and tag `v0.2.0`.

`v0.1.0` is tagged in git but was never published; PyPI starts at `0.2.0`.
That is fine — PyPI does not care that a number is missing.

## When it fails

| Symptom | Cause |
|---|---|
| `invalid-publisher` / OIDC rejected | A field on the PyPI form disagrees with reality. The usual one is "Repository name": it wants `note-cli`, not `notegraph`. |
| `File already exists` | That version is spent. Bump to the next number; deleting the PyPI release does not free it. |
| Workflow never starts | The tag was pushed without `origin`, or does not match `v*`. `git push origin v0.3.0`. |
| Publishes the wrong version | `pyproject.toml` and the tag disagreed. The tag is cosmetic; the build reads `pyproject.toml`. |

A failed publish is safe to retry once the cause is fixed — except
`File already exists`, which is the one that costs a version number.

## Current state

CI runs on every push to `main` and on pull requests: the six checks across
Python 3.9–3.13, plus a build and `twine check`. All five versions passed on
`8b734db`, which is the only evidence behind `requires-python = ">=3.9"` —
widen or narrow the matrix and that declaration together.
