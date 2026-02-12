#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

MANIFEST_FILE="custom_components/aquarea/manifest.json"

echo -e "${GREEN}=== Aquarea Integration (heishamon-homeassistant) Release Tool ===${NC}\n"

# Check if we're in the right directory
if [ ! -f "$MANIFEST_FILE" ]; then
    echo -e "${RED}Error: $MANIFEST_FILE not found.${NC}"
    echo -e "${RED}This script must be run from the heishamon-homeassistant repository root.${NC}"
    exit 1
fi

# Verify we're in the correct repo
REPO_NAME=$(git remote get-url origin 2>/dev/null | grep -o 'heishamon-homeassistant' || echo "")
if [ "$REPO_NAME" != "heishamon-homeassistant" ]; then
    echo -e "${RED}Error: This doesn't appear to be the heishamon-homeassistant repository.${NC}"
    echo -e "${RED}Current remote: $(git remote get-url origin 2>/dev/null || echo 'not a git repo')${NC}"
    exit 1
fi

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

# Get current version from manifest.json
CURRENT_MANIFEST_VERSION=$(jq -r '.version' "$MANIFEST_FILE")
echo -e "Current version in manifest.json: ${YELLOW}$CURRENT_MANIFEST_VERSION${NC}"

# Get latest GitHub release
LATEST_RELEASE=$(gh release list --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null || echo "None")
echo -e "Latest GitHub release: ${YELLOW}$LATEST_RELEASE${NC}"

# Check if there are uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "\n${RED}Warning: You have uncommitted changes. Please commit or stash them first.${NC}"
    git status --short
    exit 1
fi

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
echo "4. Create GitHub release with auto-generated changelog"
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

# Create GitHub release
echo -e "\n${GREEN}Creating GitHub release...${NC}"
gh release create "$NEW_VERSION" \
    --title "$NEW_VERSION" \
    --generate-notes

echo -e "\n${GREEN}✓ Release $NEW_VERSION created successfully!${NC}"
echo -e "View it at: $(gh release view $NEW_VERSION --json url --jq '.url')"
