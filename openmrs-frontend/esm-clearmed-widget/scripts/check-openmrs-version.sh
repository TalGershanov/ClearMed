#!/usr/bin/env bash
# Diagnoses/fixes the "does not refer to a federated module" dev-shell crash.
#
# Background: dev3.openmrs.org (the demo server `npm start` proxies to for its
# import map -- see README.md "Pinned to a moving target" section) runs
# whatever OpenMRS just pushed to the npm `next` dist-tag, not the stable
# `latest` release. If our pinned versions fall behind that tag, every core
# app (nav bar, login, help menu, ...) dies with "does not refer to a
# federated module" and the dev shell is a blank page. This script reports
# whether our pin is still current and, if not, updates package.json for you.
#
# Usage: npm run check-openmrs-version

set -euo pipefail
cd "$(dirname "$0")/.."

PINNED=$(node -p "require('./package.json').devDependencies.openmrs")
NEXT=$(npm view openmrs dist-tags.next)

echo "Pinned in package.json: $PINNED"
echo "Currently published as 'next':   $NEXT"

if [ "$PINNED" = "$NEXT" ]; then
  echo "In sync -- no change needed."
  exit 0
fi

echo
echo "Out of sync. Re-pinning openmrs, @openmrs/esm-framework, and @openmrs/esm-styleguide to $NEXT ..."
node -e "
  const fs = require('fs');
  const path = './package.json';
  const pkg = JSON.parse(fs.readFileSync(path, 'utf8'));
  for (const section of ['peerDependencies', 'devDependencies']) {
    for (const dep of ['@openmrs/esm-framework', '@openmrs/esm-styleguide']) {
      if (pkg[section] && pkg[section][dep]) pkg[section][dep] = '$NEXT';
    }
  }
  pkg.devDependencies.openmrs = '$NEXT';
  fs.writeFileSync(path, JSON.stringify(pkg, null, 2) + '\n');
"

cat <<EOF

package.json updated to $NEXT. Now run, in order:

  npm install        # do NOT delete package-lock.json or node_modules first --
                      # see README.md "EMFILE: too many open files" section
  npm ls openmrs @openmrs/esm-framework @openmrs/esm-styleguide
  # fully stop any running "npm start" (a live dev server never picks up a
  # dependency change on its own) and start fresh:
  npm start -- --backend https://dev3.openmrs.org --routes routes.registry.fixed.json
EOF
