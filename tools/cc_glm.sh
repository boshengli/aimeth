#!/bin/bash
# Run Claude Code (official GLM Coding Plan tool) against the Zhipu Anthropic-compatible endpoint.
# Key is read from ~/.config/aimeth/api.env and exported only to this process; never printed.
set -euo pipefail
export ANTHROPIC_AUTH_TOKEN="$(grep -E "^ZHIPU_API_KEY=" ~/.config/aimeth/api.env | head -1 | cut -d= -f2- | tr -d "\"'")"
export ANTHROPIC_BASE_URL="https://open.bigmodel.cn/api/anthropic"
export API_TIMEOUT_MS=3000000
export CLAUDE_CONFIG_DIR=/data/libs/aimeth/cc/config
export DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 DISABLE_TELEMETRY=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.3-flash ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.3 ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.3
cd /data/libs/aimeth/cc/work
exec /data/libs/aimeth/envs/cc/bin/claude "$@"
