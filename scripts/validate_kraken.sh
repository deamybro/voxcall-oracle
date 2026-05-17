#!/usr/bin/env sh
set -eu

echo "Checking Kraken CLI..."
kraken status -o json

echo "Checking xStock ticker..."
kraken ticker AAPLx/USD --asset-class tokenized_asset -o json

echo "Checking paper account..."
kraken paper status -o json || true

echo "Placing tiny paper xStock order..."
kraken paper buy AAPLx/USD 0.01 --type market -o json

echo "Kraken CLI validation complete."
