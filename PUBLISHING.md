# Publishing to PyPI

The packaging is ready: `pyproject.toml` has full metadata, the package builds
cleanly (`python -m pip wheel . -w dist --no-deps`), and installing the built
wheel gives a working `logsift` command — all verified locally, not just
assumed. [.github/workflows/publish.yml](.github/workflows/publish.yml) builds
and publishes automatically whenever a GitHub Release is published, using
PyPI's Trusted Publishing so no API token has to be stored in this repo.

Four steps are left, and they need your PyPI account, not more code:

1. **Create a PyPI account** at [pypi.org/account/register](https://pypi.org/account/register/),
   if you don't have one.
2. **Register a Trusted Publisher** at
   [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/):
   - PyPI project name: `accesslog-sift` (the name `logsift` is already taken
     by an unrelated project; the installed command stays `logsift` either way)
   - Owner: `Chad9100`
   - Repository: `logsift`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. **Create a `pypi` environment** on GitHub: repo → Settings → Environments →
   New environment → name it `pypi`. (Optional but recommended: add yourself
   as a required reviewer, so every publish needs a manual approval click.)
4. **Cut a release**: tag the commit (e.g. `git tag v0.1.0 && git push --tags`),
   then on GitHub go to Releases → Draft a new release → pick that tag →
   Publish release. That publish event triggers the workflow, which builds
   and uploads to PyPI.

After that, anyone can `pip install accesslog-sift` and get the `logsift`
command. Future releases: bump `version` in `pyproject.toml`, commit, tag, and
publish a new GitHub Release the same way.
