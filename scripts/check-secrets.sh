#!/usr/bin/env bash
# 提交前安全检查：确认敏感文件未被 git 跟踪，且待提交源文件无真实密钥
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
FAIL=0

echo "🔒 密钥安全检查 …"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "⚠️  尚未 git init，跳过 index 检查"
  exit 0
fi

# 1) 这些路径绝不允许出现在 git index
FORBIDDEN=(
  ".livekit.env"
  "agent-py/.env.local"
  "agent-web/.env"
  "agent-web/.livekit-cloud.api.key.md"
)
for f in "${FORBIDDEN[@]}"; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo -e "${RED}✗ 敏感文件已被 git 跟踪: $f${NC}"
    FAIL=1
  fi
done

# 2) 模拟 add，列出将被跟踪的文件
TRACKED=()
while IFS= read -r line; do
  TRACKED+=("${line#add }")
done < <(git add -n . 2>/dev/null)

# 3) 在待提交文件中扫描疑似真实密钥（排除文档、锁文件、示例）
#    只匹配赋值语句右侧的值，避免误报 X-Api-Key 等标识符
VALUE_PATTERN='=(sk-[a-zA-Z0-9]{20,}|API[A-Za-z0-9]{10,})'

for file in "${TRACKED[@]}"; do
  [ -f "$file" ] || continue
  case "$file" in
    *.example|uv.lock|package-lock.json|README.md|check-secrets.sh) continue ;;
  esac
  if rg -q "$VALUE_PATTERN" "$file" 2>/dev/null; then
    if rg -q 'sk-xxxxxxxx|APIxxxxxxxx|xxxxxxxxxxxx|your-project|devkey' "$file" 2>/dev/null; then
      continue
    fi
    echo -e "${RED}✗ 待提交文件含疑似真实密钥: $file${NC}"
    FAIL=1
  fi
done

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}✓ 通过（${#TRACKED[@]} 个文件待提交，无敏感路径）${NC}"
  exit 0
else
  echo -e "${RED}✗ 请修复后再提交${NC}"
  exit 1
fi
