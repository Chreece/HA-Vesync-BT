#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/homeassistant/config" >&2
  exit 2
fi

CONFIG_DIR="$1"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)/custom_components/ha_vesync_bt"
DEST="$CONFIG_DIR/custom_components/ha_vesync_bt"

mkdir -p "$CONFIG_DIR/custom_components"
rm -rf "$DEST"
cp -a "$SOURCE" "$DEST"

echo "Installed HA-VeSync-BT to:"
echo "$DEST"
echo "Restart Home Assistant, wake the scale, then add HA-VeSync-BT from Devices & services."
