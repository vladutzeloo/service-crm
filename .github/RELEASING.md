# Cutting a release

End-to-end this should take ~2 minutes and zero clicks in the GitHub UI.

## How releases work now

Two workflows split the job:

- **`auto-tag.yml`** watches `main` for commits that change the `VERSION`
  file. When it sees one, it validates `VERSION` + `CHANGELOG.md`,
  creates and pushes the matching `vX.Y.Z` tag, and dispatches
  `release.yml` for that tag.
- **`release.yml`** does the actual release work (verify, test, build,
  publish) whenever a `vX.Y.Z` tag exists. It fires from three places:
  - a `workflow_dispatch` from `auto-tag.yml` (the normal path —
    tags pushed by `GITHUB_TOKEN` don't fire `on: push: tags`, so
    `auto-tag.yml` hands off via dispatch),
  - a manual `git push origin v0.2.0` (the fallback path),
  - a manual `workflow_dispatch` run from the Actions tab (for
    re-running a failed release).

You don't run `git tag` by hand anymore. **Bumping `VERSION` and pushing
the commit is the release trigger.**

## 0. Preconditions

- You're on `main`, fully up to date, working tree clean.
- CI is green on the commit you intend to release.
- You have permission to push to `main` (or you go through a PR — the
  end of that flow is a merge to `main`, which is what triggers
  `auto-tag.yml`).

## 1. Pick the version

Use [SemVer](https://semver.org/). During 0.x:

- Breaking change to API, schema, or CLI → bump **MINOR**.
- Backwards-compatible feature → bump **MINOR**.
- Bug fix only → bump **PATCH**.

From 1.0 onwards, bumps follow the standard SemVer rules.

## 2. Update VERSION + CHANGELOG.md in one commit

```bash
git checkout main && git pull
echo "0.2.0" > VERSION
$EDITOR CHANGELOG.md   # see "What goes in the CHANGELOG edit" below
git add VERSION CHANGELOG.md
git commit -m "release: 0.2.0"
git push origin main
```

### What goes in the CHANGELOG edit

Keep-a-Changelog 1.1.0 requires three things on every release:

1. Rename `## [Unreleased]` to `## [0.2.0] - YYYY-MM-DD` (today's date).
2. Add a fresh empty `## [Unreleased]` block at the top.
3. **Update the comparison links at the bottom of the file.** Before:
   ```
   [Unreleased]: https://github.com/vladutzeloo/service-crm/compare/v0.1.0...HEAD
   [0.1.0]: https://github.com/vladutzeloo/service-crm/releases/tag/v0.1.0
   ```
   After:
   ```
   [Unreleased]: https://github.com/vladutzeloo/service-crm/compare/v0.2.0...HEAD
   [0.2.0]: https://github.com/vladutzeloo/service-crm/compare/v0.1.0...v0.2.0
   [0.1.0]: https://github.com/vladutzeloo/service-crm/releases/tag/v0.1.0
   ```
   The very first release links straight to the tag; every subsequent
   release uses a compare-link against its predecessor, and
   `Unreleased` always points at the newest tag.

`auto-tag.yml` fires on that push. It:

1. Reads `VERSION`, validates SemVer.
2. Confirms `CHANGELOG.md` has a `## [0.2.0]` section. If not, **fails
   loudly** — see "Re-triggering after a CHANGELOG fix" below; a plain
   `git push` of a CHANGELOG-only fix will **not** re-run `auto-tag.yml`.
3. Skips if `v0.2.0` already exists on origin (so re-running the same
   commit, or pushing an unrelated commit later, is a no-op).
4. Pushes `v0.2.0`.
5. Dispatches `release.yml` for `v0.2.0`.

`release.yml` then runs the test suite, builds the sdist + wheel, and
creates the GitHub Release with the matching CHANGELOG section as the
body.

Pre-1.0 releases and any tag containing a hyphen (`v0.5.0-rc.1`,
`v1.0.0-beta.2`) are marked as **pre-release** automatically.

## 3. Manual / fallback path

If `auto-tag.yml` is disabled, broken, or you need to tag a commit that
isn't the tip of `main`, the original tag-driven path still works:

```bash
git tag -a v0.2.0 -m "v0.2.0"
git push origin v0.2.0
```

That tag push fires `release.yml` directly.

## 4. If something goes wrong

### Re-triggering after a CHANGELOG fix

`auto-tag.yml` listens on `paths: ['VERSION']`. If the SemVer / CHANGELOG
check fails (or the run errors out mid-flight) **no tag was pushed**, so
nothing is published yet — but a fix-up commit that only touches
`CHANGELOG.md` won't re-run the workflow. Three ways to re-trigger:

1. **Easiest** — run `auto-tag.yml` from the Actions tab via
   "Run workflow" (`workflow_dispatch`). It re-reads `VERSION` from the
   chosen branch and proceeds.
2. **Re-touch `VERSION`** in the same fix-up commit, e.g.
   ```bash
   $EDITOR CHANGELOG.md
   echo "0.2.0" > VERSION   # rewrite with the same value to bump mtime
   git add CHANGELOG.md VERSION
   git commit -m "fix CHANGELOG for 0.2.0"
   git push origin main
   ```
   The path filter triggers on any change to the file's content, so
   rewriting with the same value works (the commit still touches the
   file). If you only want a fully no-op `VERSION` change, append a
   trailing newline instead.
3. **Fall back to the manual tag path** (section 3 above).

### Replacing a botched tag

To replace a tag **before** anyone has pulled it:
```bash
git tag -d v0.2.0
git push --delete origin v0.2.0
# …fix the underlying issue, then either:
#   - bump VERSION + CHANGELOG again (auto-tag re-runs), or
#   - re-tag manually (step 3).
```
Never re-point a tag that has already been published in a release;
cut a new patch version instead.

### Re-running a partially-published release

The `release.yml` job is idempotent. If tests or the artifact upload
failed after the tag was pushed, re-run from the Actions tab via
`workflow_dispatch` and pass the existing tag — the GitHub Release
will be created (or updated) without a new tag.
