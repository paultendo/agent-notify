#!/usr/bin/env bash
# shellcheck disable=SC2016  # backticks in the test messages are literal markdown
# The webhook formatter, run straight from the script: ntfy's target and body, and plain text for phones
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
formatter="$(mktemp)"
trap 'rm -f "$formatter"' EXIT
sed -n "/<<'PYWEBHOOK'/,/^PYWEBHOOK\$/p" "$repo_root/agent-notify" | sed '1d;$d' > "$formatter"

# title message agent category url preset telegram_chat_id ntfy_topic session_id
run() { python3 "$formatter" "$@"; }

python3 - "$(run "Codex: Done" "Hi" "Codex" approval "https://ntfy.sh/alerts" ntfy "" "" "")" <<'PY'
import json, sys
target, body = sys.argv[1].split("\n", 1)
data = json.loads(body)
assert target == "https://ntfy.sh/", target
assert data["topic"] == "alerts" and data["priority"] == 4, data
PY

python3 - "$(run "t" "m" "Codex" error "https://example.com/ntfy/builds" ntfy "" "" "")" <<'PY'
import json, sys
target, body = sys.argv[1].split("\n", 1)
assert target == "https://example.com/ntfy/", target
assert json.loads(body)["topic"] == "builds"
PY

python3 - "$(run "t" "m" "Codex" completion "https://ntfy.sh" ntfy "" "alerts" "")" <<'PY'
import json, sys
target, body = sys.argv[1].split("\n", 1)
assert target == "https://ntfy.sh/", target
assert json.loads(body)["topic"] == "alerts"
PY

message=$'## Done\n\n**Fixed** the `setup` step:\n\n- one\n- two\n\nSee [the PR](https://example.com/pr).'
python3 - "$(run "Codex: Done" "$message" "Codex" completion "https://ntfy.sh/alerts" ntfy "" "" "")" <<'PY'
import json, sys
data = json.loads(sys.argv[1].split("\n", 1)[1])
assert data["message"] == "Done Fixed the setup step: one two See the PR.", data["message"]
PY

long="$(printf 'word%.0s ' $(seq 1 120))"
python3 - "$(run "t" "$long" "Codex" completion "https://ntfy.sh/alerts" ntfy "" "" "")" <<'PY'
import json, sys
m = json.loads(sys.argv[1].split("\n", 1)[1])["message"]
assert m.endswith("word…") and len(m) <= 301, m
PY

# ntfy sends markdown only when asked, for its web app
python3 - "$(CODEX_NOTIFY_NTFY_MARKDOWN=1 run "t" "**Done** in \`setup\`" "Codex" completion "https://ntfy.sh/alerts" ntfy "" "" "")" <<'PY'
import json, sys
data = json.loads(sys.argv[1].split("\n", 1)[1])
assert data["markdown"] is True and data["message"] == "**Done** in `setup`", data
PY

# Each service gets the agent's formatting in its own dialect
formatted=$'**Done** in `setup` & <b>. See [the PR](https://example.com/pr).'
python3 - "$(run "Codex: **Done**" "$formatted" "Codex" completion "https://api.telegram.org/botX/sendMessage" telegram "42" "" "")" <<'PY'
import json, sys
text = json.loads(sys.argv[1].split("\n", 1)[1])["text"]
assert "<b>✅ Codex: Done</b>" in text, text
assert '<b>Done</b> in <code>setup</code> &amp; &lt;b&gt;. See <a href="https://example.com/pr">the PR</a>.' in text, text
PY
python3 - "$(run "Codex: **Done**" "$formatted" "Codex" completion "https://hooks.slack.com/services/x" slack "" "" "")" <<'PY'
import json, sys
att = json.loads(sys.argv[1].split("\n", 1)[1])["attachments"][0]
assert att["title"].endswith("Codex: Done"), att
assert att["text"] == "*Done* in `setup` &amp; &lt;b&gt;. See <https://example.com/pr|the PR>.", att["text"]
PY
python3 - "$(run "Codex: **Done**" "$formatted" "Codex" completion "https://discord.com/api/webhooks/x" discord "" "" "")" <<'PY'
import json, sys
embed = json.loads(sys.argv[1].split("\n", 1)[1])["embeds"][0]
assert embed["description"] == "**Done** in `setup` & <b>. See [the PR](https://example.com/pr).", embed
PY
python3 - "$(run "Codex: **Done**" "$formatted" "Codex" completion "https://example.com/hook" generic "" "" "")" <<'PY'
import json, sys
data = json.loads(sys.argv[1].split("\n", 1)[1])
assert data["message"].startswith("**Done** in `setup`") and data["message_plain"].startswith("Done in setup &"), data
PY

# Other presets post to the URL as given
python3 - "$(run "t" "m" "Codex" completion "https://hooks.slack.com/services/x" slack "" "" "")" <<'PY'
import sys
assert sys.argv[1].split("\n", 1)[0] == "https://hooks.slack.com/services/x"
PY

echo "webhook: all cases pass"
