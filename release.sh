#!/bin/bash
# Generic release tool for Home Assistant custom component repositories.
#
# This script is portable: copy it as-is to the root of any git clone
# (with a GitHub origin) that has a custom_components/<name>/manifest.json,
# and it will auto-detect everything it needs.
#
# Optional configuration:
#   MAINTAINERS="login1,login2"   Comma-separated list of GitHub logins to
#                                 exclude from the "thank you" section.
#                                 Defaults to the repository owner.
#   .github/release-maintainers   One login per line, alternative to $MAINTAINERS.
#
# Requirements: git, gh (GitHub CLI), jq
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Auto-detection of repository, owner and component
# ---------------------------------------------------------------------------

ORIGIN_URL=$(git remote get-url origin 2>/dev/null || true)
if [ -z "$ORIGIN_URL" ]; then
    echo -e "${RED}Error: not a git repository (or no 'origin' remote).${NC}"
    exit 1
fi

# Extract owner/repo from URLs like:
#   git@github.com:owner/repo.git
#   https://github.com/owner/repo.git
#   ssh://git@github.com/owner/repo.git
#   ssh://git@github.com:22/owner/repo.git
OWNER_REPO=$(printf '%s' "$ORIGIN_URL" | sed -E '
    s#^[a-zA-Z][a-zA-Z0-9+.-]*://##;
    s#^[^/@]+@##;
    s#^github\.com(:[0-9]+)?[:/]##;
    s#\.git$##;
    s#/$##
')
if ! printf '%s\n' "$OWNER_REPO" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'; then
    echo -e "${RED}Error: could not parse owner/repo from origin URL: $ORIGIN_URL${NC}"
    echo -e "${RED}Only GitHub remotes are supported.${NC}"
    exit 1
fi
OWNER=${OWNER_REPO%%/*}
REPO=${OWNER_REPO#*/}

# Find the component manifest. If several components exist, prefer the one
# matching the repository name, otherwise ask the user.
COMPONENT=""
shopt -s nullglob
MANIFESTS=(custom_components/*/manifest.json)
shopt -u nullglob

if [ ${#MANIFESTS[@]} -eq 0 ]; then
    echo -e "${RED}Error: no custom_components/*/manifest.json found.${NC}"
    echo -e "${RED}This script only supports HACS-style custom component repositories.${NC}"
    exit 1
elif [ ${#MANIFESTS[@]} -eq 1 ]; then
    MANIFEST_FILE=${MANIFESTS[0]}
else
    for f in "${MANIFESTS[@]}"; do
        if [ "$(basename "$(dirname "$f")")" = "$REPO" ]; then
            MANIFEST_FILE=$f
            break
        fi
    done
    if [ -z "$MANIFEST_FILE" ]; then
        echo -e "${YELLOW}Several components found:${NC}"
        select f in "${MANIFESTS[@]}"; do
            MANIFEST_FILE=$f
            break
        done
    fi
fi
COMPONENT=$(basename "$(dirname "$MANIFEST_FILE")")

echo -e "${GREEN}=== $REPO Release Tool ===${NC}"
echo -e "Repository: ${YELLOW}$OWNER_REPO${NC}, component: ${YELLOW}$COMPONENT${NC}\n"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed. Please install it first.${NC}"
    echo "Visit: https://cli.github.com/"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is not installed. Please install it first.${NC}"
    exit 1
fi

# Fetch latest tags from remote
echo -e "\n${GREEN}Fetching latest tags from remote...${NC}"
git fetch --tags --quiet

# Get current version from manifest.json
CURRENT_MANIFEST_VERSION=$(jq -r '.version' "$MANIFEST_FILE")
echo -e "Current version in manifest.json: ${YELLOW}$CURRENT_MANIFEST_VERSION${NC}"

# Get latest GitHub release
LATEST_RELEASE=$(gh release list --repo "$OWNER_REPO" --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null || echo "None")
echo -e "Latest GitHub release: ${YELLOW}$LATEST_RELEASE${NC}"

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo -e "\n${YELLOW}Warning: You're on branch '$CURRENT_BRANCH', not 'main'.${NC}"
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Prompt for new version
echo -e "\n${GREEN}Enter new version number (e.g., 2.5.0):${NC}"
read -p "Version: " NEW_VERSION

# Validate version format
if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid version format. Use semantic versioning (e.g., 2.5.0)${NC}"
    exit 1
fi

# Check if tag already exists
if git rev-parse "$NEW_VERSION" >/dev/null 2>&1; then
    echo -e "${RED}Error: Tag $NEW_VERSION already exists${NC}"
    exit 1
fi

# Show what will be done
echo -e "\n${YELLOW}The following actions will be performed:${NC}"
echo "1. Update $MANIFEST_FILE from $CURRENT_MANIFEST_VERSION to $NEW_VERSION"
echo "2. Commit the change with message: 'Bump version to $NEW_VERSION'"
echo "3. Create and push tag $NEW_VERSION"
echo "4. Create GitHub release with generated changelog and contributor credits"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Update manifest.json
echo -e "\n${GREEN}Updating $MANIFEST_FILE...${NC}"
jq --arg version "$NEW_VERSION" '.version = $version' "$MANIFEST_FILE" > tmp.json
mv tmp.json "$MANIFEST_FILE"
echo "Updated to version $NEW_VERSION"

# Commit the change
echo -e "\n${GREEN}Committing changes...${NC}"
git add "$MANIFEST_FILE"
git commit -m "Bump version to $NEW_VERSION"

# Create and push tag
echo -e "\n${GREEN}Creating tag $NEW_VERSION...${NC}"
git tag "$NEW_VERSION"

# Push commit and tag
echo -e "\n${GREEN}Pushing to remote...${NC}"
git push origin "$CURRENT_BRANCH"
git push origin "$NEW_VERSION"

# ---------------------------------------------------------------------------
# Generate release notes with contributor credits
# ---------------------------------------------------------------------------

echo -e "\n${GREEN}Gathering contributors for release notes...${NC}"

# Previous release date (to scope PRs/issues to this release)
PREV_TAG="$LATEST_RELEASE"
PREV_DATE=""
if [ -n "$PREV_TAG" ] && [ "$PREV_TAG" != "None" ]; then
    # Compare as epoch seconds: GitHub API returns UTC dates with 'Z', git may
    # return a local offset, so naive string comparison would be wrong.
    PREV_DATE=$(git log -1 --format=%cI "$PREV_TAG" 2>/dev/null | xargs -r -I{} date -u -d {} +%s 2>/dev/null || \
        gh api "repos/$OWNER_REPO/git/refs/tags/$PREV_TAG" --jq '.object.sha' 2>/dev/null | xargs -r git log -1 --format=%cI 2>/dev/null | xargs -r -I{} date -u -d {} +%s 2>/dev/null || true)
fi

# Maintainers whose contributions we don't thank (they maintain the project)
MAINTAINERS="${MAINTAINERS:-$OWNER}"
if [ -f .github/release-maintainers ]; then
    MAINTAINERS="$MAINTAINERS,$(paste -sd, .github/release-maintainers)"
fi

is_maintainer() {
    case ",$MAINTAINERS," in
        *",$1,"*) return 0 ;;
        *)        return 1 ;;
    esac
}

# Merge PR data: number, title, author, linked issues
gh pr list --repo "$OWNER_REPO" --state merged --limit 300 \
    --json number,title,author,closingIssuesReferences,mergedAt \
    --jq '[.[] | {number: .number, title: .title, author: (.author.login // "unknown"), issues: [.closingIssuesReferences[].number], mergedAt: .mergedAt}]' \
    > /tmp/release_prs_$$.json 2>/dev/null || echo "[]" > /tmp/release_prs_$$.json

if [ -n "$PREV_DATE" ]; then
    jq --argjson d "$PREV_DATE" '[.[] | select((.mergedAt | fromdateiso8601) > $d)]' /tmp/release_prs_$$.json > /tmp/release_prs_$$.filtered.json
    mv /tmp/release_prs_$$.filtered.json /tmp/release_prs_$$.json
fi

# Issues closed since the previous release (direct fixes, not via a PR)
gh issue list --repo "$OWNER_REPO" --state closed --limit 300 \
    --json number,title,author,closedAt \
    --jq '[.[] | {number: .number, title: .title, author: (.author.login // "unknown"), closedAt: .closedAt}]' \
    > /tmp/release_issues_$$.json 2>/dev/null || echo "[]" > /tmp/release_issues_$$.json

if [ -n "$PREV_DATE" ]; then
    jq --argjson d "$PREV_DATE" '[.[] | select((.closedAt | fromdateiso8601) > $d)]' /tmp/release_issues_$$.json > /tmp/release_issues_$$.filtered.json
    mv /tmp/release_issues_$$.filtered.json /tmp/release_issues_$$.json
fi

# Build notes
NOTES_FILE=/tmp/release_notes_$$.md
{
    echo "## What's Changed"
    # PR list, like GitHub's auto-generated notes
    jq -r 'if length == 0 then empty else .[] | "* \(.title) in #\(.number)" end' /tmp/release_prs_$$.json

    # ---- Contributor credits ----
    # Fetch author & title of issues fixed by the merged PRs, so their
    # reporters can be credited too.
    LINKED=$(jq '[.[].issues[]] | unique' /tmp/release_prs_$$.json)
    echo "$LINKED" | jq -r '.[]' | while read -r ISSUE_NUM; do
        gh api "repos/$OWNER_REPO/issues/$ISSUE_NUM" \
            --jq '{number: .number, title: .title, author: (.user.login // "unknown")}' 2>/dev/null
    done | jq -s '.' > /tmp/release_linked_issues_$$.json

    # PR authors, with a mention of the issues they fix
    jq -r --slurpfile linked /tmp/release_linked_issues_$$.json '
        [ .[] | select((.author | test("\\[bot\\]$|dependabot|renovate|github-actions")) | not) ][]
        | . as $pr
        | ([$linked[0][] | select(.number as $n | $pr.issues | index($n)) | "#\(.number)"] | join(", ")) as $fixes
        | "\(.author)|PR #\(.number) – \(.title)" + (if $fixes == "" then "" else " (fixes \($fixes))" end)
    ' /tmp/release_prs_$$.json > /tmp/release_thanks_$$.txt

    # Reporters of issues fixed by those PRs
    jq -r --slurpfile prs /tmp/release_prs_$$.json '
        [ $prs[0][] | .issues[] ] as $pr_linked
        | [ .[] | select((.author | test("\\[bot\\]$|dependabot|renovate|github-actions")) | not) ]
        | [ .[] | select(.number as $n | $pr_linked | index($n)) ][]
        | . as $iss
        | ([$prs[0][] | select(.issues | index($iss.number)) | "#\(.number)"] | join(", ")) as $fixedby
        | "\(.author)|issue #\(.number) – \(.title) (fixed in \($fixedby))"
    ' /tmp/release_linked_issues_$$.json >> /tmp/release_thanks_$$.txt || true

    # Reporters of issues closed since last release but not fixed via a merged PR
    jq -r --argjson linked "$LINKED" '
        [ .[] | select((.author | test("\\[bot\\]$|dependabot|renovate|github-actions")) | not) ]
        | [ .[] | select(.number as $n | $linked | index($n) | not) ][]
        | "\(.author)|issue #\(.number) – \(.title)"
    ' /tmp/release_issues_$$.json >> /tmp/release_thanks_$$.txt

    # Merge PR and issue lines for the same person, skip maintainers,
    # and only include the section if at least one credit remains.
    awk -F'|' '{ contrib[$1] = contrib[$1] (contrib[$1] == "" ? "" : "; ") $2 } END { for (who in contrib) print who "\t" contrib[who] }' \
        /tmp/release_thanks_$$.txt | sort > /tmp/release_thanks_grouped_$$.txt
    THANKS_SECTION=$(while IFS=$'\t' read -r who what; do
        if ! is_maintainer "$who"; then
            echo "- @$who for $what"
        fi
    done < /tmp/release_thanks_grouped_$$.txt)
    rm -f /tmp/release_thanks_grouped_$$.txt
    if [ -n "$THANKS_SECTION" ]; then
        echo ""
        echo "## 🙏 Thank you"
        echo ""
        echo "This release was made possible by:"
        echo "$THANKS_SECTION"
    fi

    echo ""
    if [ -n "$PREV_TAG" ] && [ "$PREV_TAG" != "None" ]; then
        echo "**Full Changelog**: https://github.com/$OWNER_REPO/compare/$PREV_TAG...$NEW_VERSION"
    fi
} > "$NOTES_FILE"

rm -f /tmp/release_prs_$$.json /tmp/release_issues_$$.json /tmp/release_thanks_$$.txt /tmp/release_linked_issues_$$.json

# Review the generated release notes before publishing
while true; do
    echo -e "\n${GREEN}Generated release notes:${NC}"
    echo -e "${YELLOW}────────────────────────────────────────${NC}"
    cat "$NOTES_FILE"
    echo -e "${YELLOW}────────────────────────────────────────${NC}"
    read -p "Publish these notes? [y]es / [e]dit / [a]bort: " -n 1 -r
    echo
    case $REPLY in
        y|Y)
            break
            ;;
        e|E)
            ${EDITOR:-${VISUAL:-vi}} "$NOTES_FILE"
            ;;
        *)
            rm -f "$NOTES_FILE"
            echo "Release aborted. The tag $NEW_VERSION was already pushed;"
            echo "delete it with: git push origin :refs/tags/$NEW_VERSION && git tag -d $NEW_VERSION"
            exit 1
            ;;
    esac
done

# Create GitHub release
echo -e "\n${GREEN}Creating GitHub release...${NC}"
gh release create "$NEW_VERSION" \
    --repo "$OWNER_REPO" \
    --title "$NEW_VERSION" \
    --notes-file "$NOTES_FILE"

rm -f "$NOTES_FILE"

RELEASE_URL=$(gh release view "$NEW_VERSION" --repo "$OWNER_REPO" --json url --jq '.url')

# The installable asset (hacs.json "zip_release"/"filename") is published by a
# workflow reacting to the "release" event. Users can only update once that
# asset is attached: a missing asset means a 404 for every Home Assistant
# user (see https://github.com/kamaradclimber/vigieau/issues/140), so wait for
# the workflow and verify the asset before announcing the release or closing
# issues. Repositories without zip_release skip this entirely.
ZIP_ASSET=""
if [ -f hacs.json ] && [ "$(jq -r '.zip_release // false' hacs.json)" = "true" ]; then
    ZIP_ASSET=$(jq -r '.filename // empty' hacs.json)
fi

# Workflow triggered on the "release" event (e.g. .github/workflows/release.yml)
RELEASE_WORKFLOW=""
for f in .github/workflows/*.yml .github/workflows/*.yaml; do
    if [ -f "$f" ] && grep -qE '^ *release:' "$f"; then
        RELEASE_WORKFLOW=$(basename "$f")
        break
    fi
done

if [ -n "$ZIP_ASSET" ]; then
    echo -e "\n${GREEN}Waiting for the release workflow to attach ${YELLOW}$ZIP_ASSET${NC}..."

    RUN_ID=""
    if [ -n "$RELEASE_WORKFLOW" ]; then
        # The workflow run may not be registered yet, poll for up to a minute.
        for _ in $(seq 1 30); do
            RUN_ID=$(gh run list --repo "$OWNER_REPO" --workflow "$RELEASE_WORKFLOW" \
                --event release --branch "$NEW_VERSION" --limit 1 \
                --json databaseId --jq '.[0].databaseId // empty' 2>/dev/null || true)
            [ -n "$RUN_ID" ] && break
            sleep 2
        done
    fi

    if [ -n "$RUN_ID" ]; then
        echo -e "Watching workflow run ${YELLOW}$RUN_ID${NC}..."
        if ! gh run watch "$RUN_ID" --repo "$OWNER_REPO" --exit-status --interval 10; then
            echo -e "\n${RED}Error: the release workflow failed for $NEW_VERSION.${NC}"
            echo "Assets were probably not published: Home Assistant updates will fail with a 404."
            echo "Re-run it with: gh run rerun $RUN_ID --failed --repo $OWNER_REPO"
            echo "No \"resolved in release\" comment was posted; the release stays published."
            exit 1
        fi
    else
        echo -e "${YELLOW}Warning: no ${RELEASE_WORKFLOW:-release} workflow run found for $NEW_VERSION, skipping the wait.${NC}"
    fi

    # Belt and braces: make sure the asset required by hacs.json is really
    # attached (the API may lag a bit behind the workflow completion).
    echo -e "\n${GREEN}Verifying release assets...${NC}"
    ASSETS_OK=""
    for _ in $(seq 1 10); do
        if gh release view "$NEW_VERSION" --repo "$OWNER_REPO" --json assets \
                --jq '.assets[].name' 2>/dev/null | grep -qx "$ZIP_ASSET"; then
            ASSETS_OK=1
            break
        fi
        sleep 3
    done

    if [ -z "$ASSETS_OK" ]; then
        echo -e "${RED}Error: $ZIP_ASSET is missing from release $NEW_VERSION.${NC}"
        echo "Home Assistant users would get a 404 when trying to update."
        if [ -n "$RUN_ID" ]; then
            echo "Re-run the workflow with: gh run rerun $RUN_ID --failed --repo $OWNER_REPO"
        fi
        echo "No \"resolved in release\" comment was posted; the release stays published."
        exit 1
    fi

    if ! gh release view "$NEW_VERSION" --repo "$OWNER_REPO" --json assets \
            --jq '.assets[].name' 2>/dev/null | grep -qx "$ZIP_ASSET.sigstore.json"; then
        echo -e "${YELLOW}Warning: $ZIP_ASSET has no sigstore bundle (signing failed).${NC}"
    fi

    echo -e "\n${GREEN}✓ Release $NEW_VERSION created successfully, ${YELLOW}$ZIP_ASSET${NC}${GREEN} verified.${NC}"
else
    echo -e "\n${GREEN}✓ Release $NEW_VERSION created successfully.${NC}"
fi
echo -e "View it at: $RELEASE_URL"

# Comment on linked issues and PRs
echo -e "\n${GREEN}Finding and commenting on linked issues/PRs...${NC}"

# Get all PR numbers from the release notes
RELEASE_BODY=$(gh release view "$NEW_VERSION" --repo "$OWNER_REPO" --json body --jq '.body')
# Extract PR numbers from both #123 format and /pull/123 URL format
PR_NUMBERS=$(echo "$RELEASE_BODY" | grep -oP '(#\K\d+|/pull/\K\d+)' | sort -u)

if [ -z "$PR_NUMBERS" ]; then
    echo -e "${YELLOW}No PRs found in release notes${NC}"
else
    # Track unique issues/PRs to comment on
    declare -A COMMENTED

    for PR_NUM in $PR_NUMBERS; do
        # Comment on the PR itself if we haven't already
        if [ -z "${COMMENTED[$PR_NUM]}" ]; then
            echo -e "  Commenting on PR #${PR_NUM}..."
            gh pr comment "$PR_NUM" --repo "$OWNER_REPO" --body "🎉 This has been included in release [$NEW_VERSION]($RELEASE_URL)" 2>/dev/null && {
                echo -e "    ${GREEN}✓${NC} Commented on PR #${PR_NUM}"
                COMMENTED[$PR_NUM]=1
            } || echo -e "    ${YELLOW}⚠${NC} Could not comment on PR #${PR_NUM} (may be closed or inaccessible)"
        fi

        # Get linked issues from the PR
        LINKED_ISSUES=$(gh pr view "$PR_NUM" --repo "$OWNER_REPO" --json closingIssuesReferences --jq '.closingIssuesReferences[].number' 2>/dev/null || echo "")

        for ISSUE_NUM in $LINKED_ISSUES; do
            if [ -z "${COMMENTED[$ISSUE_NUM]}" ]; then
                echo -e "  Commenting on linked issue #${ISSUE_NUM}..."
                gh issue comment "$ISSUE_NUM" --repo "$OWNER_REPO" --body "🎉 This has been resolved in release [$NEW_VERSION]($RELEASE_URL)" 2>/dev/null && {
                    echo -e "    ${GREEN}✓${NC} Commented on issue #${ISSUE_NUM}"
                    COMMENTED[$ISSUE_NUM]=1
                } || echo -e "    ${YELLOW}⚠${NC} Could not comment on issue #${ISSUE_NUM}"
            fi
        done
    done

    COMMENT_COUNT=${#COMMENTED[@]}
    if [ $COMMENT_COUNT -gt 0 ]; then
        echo -e "\n${GREEN}✓ Commented on $COMMENT_COUNT issue(s)/PR(s)${NC}"
    fi
fi
