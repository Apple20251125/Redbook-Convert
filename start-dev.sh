#!/usr/bin/env bash
# xhs-pdf 本地开发一键启动
#
# 用法:
#   bash start-dev.sh          启动后端 + 前端
#   bash start-dev.sh check    诊断（环境代理 / 服务状态 / 小红书连通性）
#
# 可选环境变量:
#   BACKEND_PORT   后端端口（默认 8000）
#   FRONTEND_PORT  前端端口（默认 5173）
#   PYTHON         指定 python 解释器（默认自动探测已装 fastapi/uvicorn 的）
#
# 说明:
#   进程用 nohup + disown 脱离终端，关掉终端也不会死。
#   启动前会清掉 http_proxy/https_proxy 等环境变量：这类代理在部分环境里
#   端口会随会话失效，继承旧值会让网络请求整体失败。小红书解析本身已强制直连。

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
API_DIR="$PROJECT_DIR/api"
APP_DIR="$PROJECT_DIR/app"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

log() { echo "[start-dev] $1"; }

# 探测可用的 python（需已安装 fastapi/uvicorn）
detect_python() {
  local candidates=("${PYTHON:-}" /opt/anaconda3/bin/python python3 python)
  local c
  for c in "${candidates[@]}"; do
    [ -z "$c" ] && continue
    command -v "$c" >/dev/null 2>&1 || continue
    if "$c" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
      echo "$c"
      return 0
    fi
  done
  echo ""
}

# 探测 npm
detect_npm() {
  local c
  c="$(command -v npm 2>/dev/null || true)"
  if [ -n "$c" ]; then
    echo "$c"
    return 0
  fi
  local dir
  dir=$(ls -d "$HOME"/.workbuddy/binaries/node/versions/*/bin 2>/dev/null | sort | tail -1)
  if [ -n "$dir" ] && [ -x "$dir/npm" ]; then
    echo "$dir/npm"
    return 0
  fi
  echo ""
}

# 清理沙箱/会话级代理环境变量（端口会随会话失效，继承旧值会导致请求全失败）
clean_proxy_env() {
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
}

# 启动脱离终端的后台进程（macOS 无 setsid，用 nohup + disown）
start_detached() {
  local logfile="$1"; shift
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup "$@" > "$logfile" 2>&1 &
  else
    nohup "$@" > "$logfile" 2>&1 &
    disown 2>/dev/null || true
  fi
}

# 等待端口就绪: wait_for_port <port> <max_seconds>
wait_for_port() {
  local port="$1" max="$2" i=0
  while [ "$i" -lt "$max" ]; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

port_alive() {
  local host="$1" port="$2"
  (exec 3<>"/dev/tcp/$host/$port") >/dev/null 2>&1
}

do_check() {
  echo "=== 环境代理 ==="
  local any=0 k v ep h p
  for k in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY; do
    eval "v=\${$k-}"
    [ -z "$v" ] && continue
    any=1
    ep="${v#*://}"; ep="${ep%%/*}"
    h="${ep%%:*}"; p="${ep##*:}"
    if port_alive "$h" "$p"; then
      echo "  $k = $v  -> 存活"
    else
      echo "  $k = $v  -> 已失效（端口不通）"
    fi
  done
  [ "$any" = "0" ] && echo "  无代理环境变量"

  echo ""
  echo "=== 服务状态 ==="
  for port in "$FRONTEND_PORT" "$BACKEND_PORT"; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "  $port 监听中"
    else
      echo "  $port 未监听"
    fi
  done

  echo ""
  echo "=== 小红书直连连通性 ==="
  local code
  code=$(curl -s --noproxy '*' -m 15 -o /dev/null -w "%{http_code}" "https://xhslink.cn/o/90scX2ryAVq" 2>/dev/null || echo "000")
  if [ "$code" = "302" ] || [ "$code" = "200" ]; then
    echo "  直连正常 (HTTP $code)"
  else
    echo "  直连异常 (HTTP $code) —— 网络或小红书侧问题"
  fi
}

if [ "${1:-}" = "check" ]; then
  do_check
  exit 0
fi

PYTHON_BIN="$(detect_python)"
if [ -z "$PYTHON_BIN" ]; then
  log "错误：未找到已安装 fastapi/uvicorn 的 python，请先执行：pip install -r api/requirements.txt"
  exit 1
fi

NPM_BIN="$(detect_npm)"
if [ -z "$NPM_BIN" ]; then
  log "错误：未找到 npm，请安装 Node.js 18+"
  exit 1
fi

# ---- 启动后端 ----
if lsof -nP -iTCP:"$BACKEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  log "后端 $BACKEND_PORT 已在运行, 跳过"
else
  clean_proxy_env
  start_detached "$PROJECT_DIR/backend.log" "$PYTHON_BIN" -c "import sys; sys.path.insert(0, '$API_DIR'); import uvicorn; from app import app; uvicorn.run(app, host='127.0.0.1', port=$BACKEND_PORT)"
  if wait_for_port "$BACKEND_PORT" 20; then
    log "后端就绪 -> http://127.0.0.1:$BACKEND_PORT (日志: backend.log)"
  else
    log "警告: 后端 20 秒内未就绪, 见 $PROJECT_DIR/backend.log"
  fi
fi

# ---- 启动前端 ----
if lsof -nP -iTCP:"$FRONTEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  log "前端 $FRONTEND_PORT 已在运行, 跳过"
else
  cd "$APP_DIR" || exit 1
  start_detached "$PROJECT_DIR/frontend.log" "$NPM_BIN" run dev
  if wait_for_port "$FRONTEND_PORT" 30; then
    log "前端就绪 -> http://127.0.0.1:$FRONTEND_PORT (日志: frontend.log)"
  else
    log "警告: 前端 30 秒内未就绪, 见 $PROJECT_DIR/frontend.log"
  fi
fi

echo ""
log "完成."
log "  访问前端: http://127.0.0.1:$FRONTEND_PORT/"
log "  后端 API: http://127.0.0.1:$BACKEND_PORT/api/health"
log "  诊断: bash $0 check"
log "  停止服务: lsof -nP -iTCP:$BACKEND_PORT,$FRONTEND_PORT -sTCP:LISTEN  然后 kill 对应 PID"
