# Public repository privacy

Keep personal writing rules, artwork-generation recipes, private research, raw
conversations, credentials, and employer or customer material in private authoring.
Promote only reviewed content into this repository. Intentional demo prompts,
synthetic fixtures, technical agent instructions, and reviewed engineering
decisions remain public evidence.

## Before any public upload

Install the optional local hooks in every clone:

```sh
git config --local core.hooksPath .githooks
python3 scripts/check_privacy.py --staged
python3 scripts/check_privacy.py --range origin/main HEAD
```

Check an existing hooksPath first and integrate existing hooks rather than replacing
them. Python 3 is required. The staged check reads the index; the outgoing check
reads every new commit, including content later deleted. A missing base object
fails closed: fetch the destination history and retry. New-ref pre-push checks
confirm live destination refs over the network and fail closed if unavailable. Inspect flagged object IDs
locally with Git; never paste sensitive contents into public logs or discussions.

Local hooks are opt-in and can be bypassed. GitHub API, web-editor, and connector
writes do not run them: prepare and check the exact candidate Git tree and outgoing
history locally before uploading through those paths. Do not upload private
content to a public branch merely to have CI examine it. Public branches and PRs
are visible before merge; CI only provides a second check.

## What is checked

The shared checker rejects known private paths, environment files other than a
reviewed example, raw artifacts, symlinks, submodules, selected credential formats,
private markers, image-authoring fields, local user paths, and saved notebook
execution output. It scans Git blobs and commit messages and reports categories
and object IDs without printing matched content. Keep environment examples free
of real values. Generic application prompts are allowed.

An upstream learning fork may retain existing notebook output only through exact
file hashes derived from the fixed upstream commit in the checker. Candidate
configuration cannot grant exceptions. These are compatibility exceptions, not
proof that upstream output is confidential-data-free. Any changed notebook must
clear outputs and execution counts; changing the pinned upstream revision needs
explicit code review. A shallow fork clone must fetch that revision to retain the
legacy examples. Other repositories receive no notebook-output exemptions.

The scanner is a targeted safeguard, not a full secret scanner or a guarantee of
confidentiality. Review facts, attachments, screenshots, image metadata, comments,
release files, and generated build artifacts separately. Credential scanning and
push protection remain complementary. CI does not erase historical disclosures.

If material was already exposed, remove it from current content, assess history
and other public copies, and rotate any exposed credentials. Do not rewrite
history or change repository visibility without an explicit decision.
