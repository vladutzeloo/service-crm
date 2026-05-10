# Cutting a release

End-to-end this should take ~5 minutes and zero clicks in the GitHub UI.

## 0. Preconditions

- You're on `main`, fully up to date, working tree clean.
- CI is green on the commit you intend to release.
- You have permission to push tags to `vladutzeloo/service-crm`.

## 1. Pick the version

Use [SemVer](https://semver.org/). During 0.x:

- Breaking change to API, schema, or CLI → bump **MINOR**.
- Backwards-compatible feature → bump **MINOR**.
- Bug fix only → bump **PATCH**.

From 1.0 onwards, bumps follow the standard SemVer rules.

## 2. Update the version + changelog

```bash
# 1. Update VERSION
echo "0.1.0" > VERSION

# 2. Move the Unreleased entries into a new section in CHANGELOG.md.
#    Add a release date in YYYY-MM-DD. Re-add an empty Unreleased section.
$EDITOR CHANGELOG.md

# 3. Commit
git add VERSION CHANGELOG.md
git commit -m "release: 0.1.0"
git push origin main
```

Wait for CI to go green on `main`.

## 3. Tag and push

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

The `release.yml` workflow:

1. Verifies the tag matches `VERSION` and that `CHANGELOG.md` has a section
   for it. (If either check fails, **no release is created** — fix the file,
   delete the tag, re-tag.)
2. Runs the test suite.
3. Builds the sdist + wheel.
4. Creates a GitHub Release whose body is the matching CHANGELOG section, with
   the build artifacts attached.

Pre-1.0 releases and any tag containing a hyphen (`v0.5.0-rc.1`,
`v1.0.0-beta.2`) are marked as **pre-release** automatically.

## 4. If something goes wrong

- The release job is idempotent; re-run it from the Actions tab via
  `workflow_dispatch` and pass the existing tag.
- To replace a botched tag **before** anyone has pulled it:
  ```bash
  git tag -d v0.1.0
  git push --delete origin v0.1.0
  # ...fix the issue, re-tag, re-push
  ```
  Never re-point a tag that has already been published in a release; cut a
  new patch version instead.
