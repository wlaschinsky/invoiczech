#!/bin/bash
set -e

VERSION=$1

if [ -z "$VERSION" ]; then
  echo "Použití: ./scripts/release.sh v1.5.0"
  exit 1
fi

echo "→ Vytvářím tag $VERSION"
git tag "$VERSION"

echo "→ Pushuji commity a tag"
git push && git push --tags

echo "→ Generuji changelog"
source "$(dirname "$0")/../venv/bin/activate"
echo "y" | python "$(dirname "$0")/make_changelog.py" "$VERSION"

echo "→ Commituji CHANGELOG.md"
git add CHANGELOG.md
git commit -m "docs: changelog $VERSION"
git push

echo ""
echo "✓ Verze $VERSION vydána."
