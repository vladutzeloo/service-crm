# Cutting a release

End-to-end this should take ~2 minutes and zero clicks in the GitHub UI.

## How releases work now

Two workflows split the job:

- **`auto-tag.yml`** watches `main` for commits that change the `VERSION`
  file. When it sees one, it validates `VERSION` + `CHANGELOG.md`,
  creates and pushes the matching `vX.Y.Z` tag, and dispatches
  `release.yml` for that tag.
- **`release.yml`** does the actual release work (test, build, publish)
  whenever a `vX.Y.Z` tag exists. It fires from three places:
  - the tag push from `auto-tag.yml` (the normal path),
  - a manual `git push origin v0.2.0` (the fallback path),
  - a `workflow_dispatch` run (for re-running a failed release).

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
$EDITOR CHANGELOG.md   # move Unreleased → ## [0.2.0] - YYYY-MM-DD
git add VERSION CHANGELOG.md
git commit -m "release: 0.2.0"
git push origin main
```

`auto-tag.yml` fires on that push. It:

1. Reads `VERSION`, validates SemVer.
2. Confirms `CHANGELOG.md` has a `## [0.2.0]` section. If not, **fails
   loudly** — fix the CHANGELOG and re-push.
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

- The release job is idempotent; re-run it from the Actions tab via
  `workflow_dispatch` and pass the existing tag.
- To replace a botched tag **before** anyone has pulled it:
  ```bash
  git tag -d v0.2.0
  git push --delete origin v0.2.0
  # …fix the underlying issue, then either:
  #   - bump VERSION + CHANGELOG again (auto-tag re-runs), or
  #   - re-tag manually (step 3).
  ```
  Never re-point a tag that has already been published in a release;
  cut a new patch version instead.
