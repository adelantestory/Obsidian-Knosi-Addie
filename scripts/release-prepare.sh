#!/bin/bash
set -e

# Check if version argument is provided
if [ -z "$1" ]; then
  echo "❌ Error: Version number required"
  echo "Usage: yarn release:prepare <version>"
  echo "Example: yarn release:prepare 1.0.0"
  exit 1
fi

VERSION=$1
BRANCH_NAME="$VERSION"

echo "🚀 Preparing Obsidian plugin release: $VERSION"

# Ensure we're on main and up to date
echo "📥 Ensuring main branch is up to date..."
git checkout main
git pull origin main

# Create and checkout new release branch
echo "🌿 Creating release branch: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"

# Build the Obsidian plugin
echo "🔨 Building Obsidian plugin..."
cd client/obsidian-plugin
yarn build
cd ../..

# Copy required files to root
echo "📋 Copying plugin files to root..."
cp client/obsidian-plugin/.gitignore ./.gitignore.plugin
cp client/obsidian-plugin/main.js ./main.js
cp client/obsidian-plugin/styles.css ./styles.css
cp client/obsidian-plugin/manifest.json ./manifest.json
cp client/obsidian-plugin/versions.json ./versions.json
cp client/obsidian-plugin/README.md ./README.plugin.md

# Remove all other files except the copied ones and .git
echo "🗑️  Removing non-plugin files..."
# Get list of all files except .git, the copied files, and this script
find . -maxdepth 1 -type f ! -name '.gitignore.plugin' ! -name 'main.js' ! -name 'styles.css' ! -name 'manifest.json' ! -name 'versions.json' ! -name 'README.plugin.md' -delete

# Remove all directories except .git
find . -maxdepth 1 -type d ! -name '.' ! -name '.git' ! -path './.git' -exec rm -rf {} +

# Rename files to final names
mv .gitignore.plugin .gitignore
mv README.plugin.md README.md

# Stage all changes
echo "📦 Staging changes..."
git add -A

# Commit the changes
echo "💾 Committing plugin release..."
git commit -m "Release Obsidian plugin v$VERSION

This branch contains only the files needed for Obsidian plugin distribution.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push the branch
echo "⬆️  Pushing release branch..."
git push -u origin "$BRANCH_NAME"

# Create and push tag
echo "🏷️  Creating tag: $VERSION"
git tag "$VERSION"
git push origin "$VERSION"

# Switch back to main
echo "↩️  Switching back to main branch..."
git checkout main

echo "✅ Release prepared successfully!"
echo ""
echo "📌 Release branch: $BRANCH_NAME"
echo "🏷️  Tag: $VERSION"
echo ""
echo "Next steps:"
echo "1. Create a GitHub release from tag: $VERSION"
echo "2. Attach main.js, styles.css, and manifest.json as release assets"
echo "3. Submit to Obsidian plugin marketplace if needed"
