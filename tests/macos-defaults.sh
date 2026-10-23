#!/usr/bin/env bash
set -euo pipefail

# Run with: bash tests/macos-defaults.sh
# Mock defaults and killall so tests never change macOS settings or restart Finder.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/macos-defaults-test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/bin" "$SANDBOX/state"

cat > "$SANDBOX/bin/defaults" <<'MOCK'
#!/bin/bash
set -euo pipefail
case "$2:$3" in
  -g:com.apple.trackpad.scaling) setting=trackpad; type=-float ;;
  -g:AppleShowAllExtensions) setting=finder; type=-bool ;;
  *) echo "Unexpected defaults setting: $*" >&2; exit 2 ;;
esac
file="$MOCK_STATE/$setting"
case "$1" in
  read)
    [ -f "$file" ] || exit 1
    IFS= read -r value < "$file"
    printf '%s\n' "$value"
    ;;
  write)
    [ "$4" = "$type" ] || exit 2
    [ "${MOCK_WRITE_FAILURE:-}" != "$setting" ] || exit 2
    if [ "${MOCK_VERIFY_FAILURE:-}" = "$setting" ]; then
      printf '%s\n' 'unexpected' > "$file"
    elif [ "$type" = '-float' ]; then
      awk -v value="$5" 'BEGIN { print value + 0 }' > "$file"
    else
      [ "$5" = true ] || exit 2
      printf '%s\n' 1 > "$file"
    fi
    ;;
  *) echo "Unexpected defaults command: $*" >&2; exit 2 ;;
esac
MOCK

cat > "$SANDBOX/bin/killall" <<'MOCK'
#!/bin/bash
[ "$#" -eq 1 ] && [ "$1" = Finder ]
MOCK
chmod +x "$SANDBOX/bin/defaults" "$SANDBOX/bin/killall"

NOTICE='==> Trackpad tracking speed changed. A restart may be required for the change to take effect.'
SUCCESS='==> all defaults applied and verified'

run_case() {
  local label="$1" initial="$2" expected_status="$3" expected_notices="$4"
  local output status=0 notices
  if [ "$initial" != '<keep>' ]; then
    rm -f "$SANDBOX/state/trackpad" "$SANDBOX/state/finder"
    if [ "$initial" != '<unset>' ]; then
      printf '%s\n' "$initial" > "$SANDBOX/state/trackpad"
    fi
  fi

  output="$(PATH="$SANDBOX/bin:$PATH" BASH_ENV=/dev/null \
    MOCK_STATE="$SANDBOX/state" MOCK_VERIFY_FAILURE="${5:-}" MOCK_WRITE_FAILURE="${6:-}" \
    /bin/bash "$ROOT/macos/defaults.sh" 2>&1)" || status=$?
  notices="$(printf '%s\n' "$output" | grep -Fc "$NOTICE" || true)"
  if [ "$status" -ne "$expected_status" ] || [ "$notices" -ne "$expected_notices" ]; then
    printf 'FAIL: %s (status=%s, notices=%s)\n%s\n' "$label" "$status" "$notices" "$output" >&2
    exit 1
  fi
  if [ "$expected_status" -eq 0 ]; then
    if ! printf '%s\n' "$output" | grep -Fqx "$SUCCESS"; then
      printf 'FAIL: %s did not report successful verification\n%s\n' "$label" "$output" >&2
      exit 1
    fi
  elif printf '%s\n' "$output" | grep -Fqx "$SUCCESS"; then
    printf 'FAIL: %s reported success after a failure\n%s\n' "$label" "$output" >&2
    exit 1
  fi
  if [ "$expected_notices" -eq 1 ] && [ "${output##*$'\n'}" != "$NOTICE" ]; then
    printf 'FAIL: %s restart notice was not the final line\n%s\n' "$label" "$output" >&2
    exit 1
  fi
  printf 'PASS: %s\n' "$label"
}

run_case 'changed speed' 1.5 0 1
run_case 'rerun after a change' '<keep>' 0 0
run_case 'previously unset speed' '<unset>' 0 1
run_case 'unchanged speed' 3 0 0
run_case 'equivalent decimal speed' 3.0 0 0
run_case 'equivalent trailing-zero speed' 3.000 0 0
run_case 'trackpad verification failure' 1.5 1 0 trackpad
run_case 'Finder verification failure' 1.5 1 0 finder
run_case 'trackpad write failure' 1.5 2 0 '' trackpad
run_case 'Finder write failure' 1.5 2 0 '' finder
