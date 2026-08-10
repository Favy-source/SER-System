#!/usr/bin/env bash
# Progress of the RAVDESS video fetch. Run from the repo root.
cd "$(dirname "$0")/.." || exit 1
SP=/tmp/claude-1000/-home-favour-nwachukwu-Downloads-SER-System/194ef35c-a604-4d04-a843-df89f59ad51d/scratchpad
n=$(ls datasets/processed/landmarks/*.npy 2>/dev/null | wc -l)
echo "landmarks: $n / 1248  ($(( n * 100 / 1248 ))%)"
if pgrep -x python3 >/dev/null 2>&1 || pgrep -f 'fetch_ravdess_video.py' >/dev/null 2>&1; then
  echo "status   : running"
else
  echo "status   : not running"
fi
echo "actors   : $(ls datasets/processed/landmarks/*.npy 2>/dev/null | sed 's/.*-//;s/\.npy//' | sort -u | tr '\n' ' ')"
df -h / | awk '/\/$/{print "disk     : "$4" free ("$5" used)"}'
[ -f "$SP/fetch_video.log" ] && { echo "--- last log lines ---"; grep -aE '^Actor_|landmarks:|downloaded' "$SP/fetch_video.log" | tail -4; }
