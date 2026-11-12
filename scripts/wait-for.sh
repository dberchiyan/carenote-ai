#!/usr/bin/env bash
# Usage: wait-for.sh <url> <name> <timeout-seconds>
set -euo pipefail
url=$1 name=$2 timeout=${3:-60}
deadline=$((SECONDS + timeout))
printf "Waiting for %s " "$name"
until curl -fs -o /dev/null "$url"; do
  if (( SECONDS >= deadline )); then
    echo " timed out after ${timeout}s ($url)"
    exit 1
  fi
  printf "."
  sleep 2
done
echo " ready"
