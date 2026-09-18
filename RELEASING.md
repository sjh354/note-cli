# Releasing

Publishing runs on a `v*` tag via `.github/workflows/release.yml`, using PyPI
**Trusted Publishing** — there is no API token to create or store.

## One-time setup (a human must do this; it cannot be scripted from here)

1. Create the project on PyPI, or claim the name: <https://pypi.org/manage/account/publishing/>
2. Add a **pending publisher** with exactly these values:

   | Field | Value |
   |---|---|
   | PyPI project name | `note-cli` |
   | Owner | `sjh354` |
   | Repository name | `note-cli` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. In the GitHub repo, create an environment named `pypi`
   (Settings → Environments → New environment).

Until step 2 is done, pushing a tag runs the workflow and it fails at the
publish step. Nothing else breaks.

## Each release

1. Update `CHANGELOG.md`: move the unreleased section under the new version.
2. Bump `version` in `pyproject.toml`.
3. Verify locally — the same three the CI runs:

       for m in store graph goal render; do python -m note_cli.$m; done
       python -m note_cli._concurrency_check
       python -m note_cli._cli_check

4. Verify the artifacts build and that `SKILL.md` is inside the wheel
   (`note skill --install` reads it from there, so a missing file breaks the
   agent workflow without breaking any test):

       python -m build
       python -m twine check dist/*
       python -m zipfile -l dist/*.whl | grep SKILL.md

5. Commit, tag, push:

       git commit -am "release: 0.x.0"
       git tag -a v0.x.0 -m "note-cli 0.x.0"
       git push origin main && git push origin v0.x.0
