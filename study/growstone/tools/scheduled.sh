#!/usr/bin/env bash
# Run the GrowStone collectors on a schedule matched to how fast each source changes.
#
#   ./scheduled.sh install               add the jobs to your crontab (safe to repeat)
#   ./scheduled.sh uninstall             remove them
#   ./scheduled.sh status                show the jobs and how the latest runs went
#   ./scheduled.sh daily|weekly|monthly  run one set now (this is what cron calls)
#
# daily    04:17       Reddit (new threads, changed comment counts, mentions, images),
#                      videos linked anywhere, linked images and clips, thumbnails
# weekly   Mon 05:23   Google Play and App Store listings and screenshots; all three
#                      wikis (changed pages, new images); YouTube search if a key is set
# monthly  3rd 06:41   Play listings newly archived by the Wayback Machine; web pages
#                      linked from the corpus
#
# Every set ends by rebuilding the search index (media.py rebuilds the gallery).
# The collectors are incremental, so a run fetches only what changed. Runs never
# overlap (one lock; a later run waits up to 3 h), each step has a time limit,
# and a failed step does not stop the rest. Logs: corpus/logs/<date>_<set>.log,
# kept 90 days. A contact and optional keys go in tools/scheduled.env (gitignored):
#   GS_RESEARCH_UA="growstone-research/0.1 (contact: you@example.com)"
#   YOUTUBE_API_KEY=...
#   IMGUR_CLIENT_ID=...
set -uo pipefail

TOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CORPUS=$(cd "$TOOLS/.." && pwd)/corpus
LOGS=$CORPUS/logs
PY=${PYTHON:-$(command -v python3)}
BEGIN="# growstone-research: managed by $TOOLS/scheduled.sh"
END="# end growstone-research"

cron_block() {
  cat <<EOF
$BEGIN
17 4 * * * PYTHON=$PY $TOOLS/scheduled.sh daily >/dev/null 2>&1
23 5 * * 1 PYTHON=$PY $TOOLS/scheduled.sh weekly >/dev/null 2>&1
41 6 3 * * PYTHON=$PY $TOOLS/scheduled.sh monthly >/dev/null 2>&1
$END
EOF
}

crontab_without_block() {
  crontab -l 2>/dev/null | sed "/^# growstone-research:/,/^$END/d"
}

step() {  # step <time limit> <script> [args...]
  local limit=$1 start=$SECONDS rc took
  shift
  echo "== $(date '+%F %T') $*"
  timeout --kill-after=60 "$limit" "$PY" -u "$@"
  rc=$?
  took=$(( (SECONDS - start + 59) / 60 ))
  if [ "$rc" -eq 0 ]; then
    SUMMARY+=("ok      ${took}m  $*")
  else
    SUMMARY+=("FAILED  ${took}m  $* (exit $rc$([ "$rc" -eq 124 ] && echo ', hit the time limit'))")
    FAILED=1
  fi
}

run_set() {
  local kind=$1 log
  mkdir -p "$LOGS"
  log="$LOGS/$(date +%F)_$kind.log"
  exec 9>"$LOGS/.lock"
  if ! flock -w 10800 9; then
    echo "$(date '+%F %T') skipped: another run held the lock for 3 hours" >> "$log"
    return 1
  fi
  exec >>"$log" 2>&1
  if [ -f "$TOOLS/scheduled.env" ]; then
    set -a; . "$TOOLS/scheduled.env"; set +a
  fi
  cd "$TOOLS" || return 1
  SUMMARY=(); FAILED=0
  echo "### $kind run started $(date '+%F %T')"
  case $kind in
    daily)
      step 4h reddit.py --media
      step 1h youtube_index.py --from-corpus
      step 2h media.py linked
      step 1h media.py thumbs ;;
    weekly)
      step 1h play_store.py
      step 2h media.py store
      step 3h fandom_wiki.py --images
      if [ -n "${YOUTUBE_API_KEY:-}" ]; then step 1h youtube_index.py --from-corpus --search; fi ;;
    monthly)
      step 3h media.py history
      step 3h web_pages.py --from-corpus --depth 1 ;;
  esac
  step 30m corpus_index.py build
  echo "### $kind run finished $(date '+%F %T')"
  printf '%s\n' "${SUMMARY[@]}"
  find "$LOGS" -name '*.log' -mtime +90 -delete
  return "$FAILED"
}

status() {
  echo "Scheduled jobs (crontab):"
  if crontab -l 2>/dev/null | grep -qF "$TOOLS/scheduled.sh"; then
    crontab -l | sed -n "/^# growstone-research:/,/^$END/p" | grep -v '^#' | sed 's/^/  /'
  else
    echo "  none; run ./scheduled.sh install"
  fi
  if [ -e "$LOGS/.lock" ] && ! flock -n "$LOGS/.lock" true; then
    echo "A run is in progress: $(ls -t "$LOGS"/*.log | head -1)"
  fi
  local kind last
  for kind in daily weekly monthly; do
    last=$(ls -1 "$LOGS"/*_"$kind".log 2>/dev/null | tail -1)
    echo
    if [ -z "$last" ]; then echo "$kind: never run"; continue; fi
    echo "$kind, latest log $last:"
    # the summary printed after the last "finished" line
    awk '/^### .* finished/ {buf = ""; f = 1; next} f && /^(ok|FAILED) / {buf = buf "  " $0 "\n"} END {printf "%s", buf}' "$last"
  done
}

case ${1:-} in
  daily|weekly|monthly) run_set "$1" ;;
  install)
    { crontab_without_block; cron_block; } | crontab - && echo "Installed:" && cron_block | grep -v '^#' ;;
  uninstall)
    crontab_without_block | crontab - && echo "Removed the growstone-research jobs from crontab" ;;
  status) status ;;
  *) sed -n '2,7p' "$0"; exit 2 ;;
esac
