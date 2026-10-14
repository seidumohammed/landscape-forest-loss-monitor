#!/usr/bin/env bash
# Downloads the six Hansen GFC v1.12 tiles that cover Ghana, Cote d'Ivoire and Cameroon.
# Resumable: re-run it if the connection drops.
set -e
B="https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12"
D="${HANSEN_DIR:-$HOME/forest-loss-data/hansen}"
mkdir -p "$D"
for t in 10N_010W 20N_010W 10N_000E 20N_000E 10N_010E 20N_010E; do
  for l in lossyear treecover2000; do
    f="Hansen_GFC-2024-v1.12_${l}_${t}.tif"
    echo "$f"
    curl -fL -C - --retry 5 -o "$D/$f" "$B/$f"
  done
done
echo "DONE"
