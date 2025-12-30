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

echo "🚀 Preparing Obsidian plugin release: $VERSION"

# Ensure we're on main and up to date
echo "📥 Ensuring main branch is up to date..."
git checkout main

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
  echo "❌ Error: You have uncommitted changes on main branch"
  echo "Please commit or stash your changes before running this script."
  echo ""
  echo "To stash: git stash"
  echo "To commit: git add . && git commit -m 'your message'"
  exit 1
fi

git pull origin main

# Install dependencies
echo "📦 Installing dependencies..."
cd client/obsidian-plugin
yarn install

# Build the Obsidian plugin
echo "🔨 Building Obsidian plugin..."
yarn build
cd ../..

# Copy required files to root
echo "📋 Copying plugin files to root..."
cp client/obsidian-plugin/main.js ./main.js
cp client/obsidian-plugin/styles.css ./styles.css
cp client/obsidian-plugin/manifest.json ./manifest.json
cp client/obsidian-plugin/versions.json ./versions.json
cp client/obsidian-plugin/README.md ./README.md


# Stage all changes
echo "📦 Staging changes..."
git add -f manifest.json main.js styles.css versions.json README.md

# Commit the changes
echo "💾 Committing plugin release..."
git commit -m "Release Obsidian plugin v$VERSION

Checking in necessary files for Obsidian plugin distribution."

# Push the branch
echo "⬆️  Pushing release branch..."
git push origin main

# Create and push tag (use refs/tags/ to be explicit)
echo "🏷️  Creating tag: $VERSION"
git tag "$VERSION"
git push origin "refs/tags/$VERSION"

# Switch back to main
echo "↩️  Reverting main branch..."
git revert HEAD --no-edit
git push origin main

echo "✅ Release prepared successfully!"
echo ""
echo "🏷️  Tag: $VERSION"
echo ""
echo "Next steps:"
echo "1. Create a GitHub release from tag: $VERSION"
echo "2. Attach main.js, styles.css, and manifest.json as release assets"
echo "3. Submit to Obsidian plugin marketplace if needed"
