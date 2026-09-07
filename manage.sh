#!/usr/bin/env bash
set -euo pipefail

WEB_UNIT="personnel-safety-agent.service"
BOT_UNIT="personnel-safety-telegram.service"
TUNNEL_UNIT="personnel-safety-tunnel.service"
TUNNEL_LOG="/home/administrator/cf-tunnel.log"

reload_units() { systemctl --user daemon-reload; }

case "${1:-status}" in
  start)
    reload_units
    systemctl --user enable --now "$WEB_UNIT"
    if grep -q '^TELEGRAM_BOT_TOKEN=.' .env 2>/dev/null; then
      systemctl --user enable --now "$BOT_UNIT"
    fi
    echo "Web: http://127.0.0.1:7861"
    echo "Local model: starts on demand; idle resources are released automatically"
    ;;
  stop)
    curl -fsS -X POST http://127.0.0.1:7861/api/local-model/stop >/dev/null 2>&1 || true
    systemctl --user stop "$BOT_UNIT" "$WEB_UNIT" 2>/dev/null || true
    ;;
  restart)
    reload_units
    systemctl --user restart "$WEB_UNIT"
    if grep -q '^TELEGRAM_BOT_TOKEN=.' .env 2>/dev/null; then
      systemctl --user restart "$BOT_UNIT"
    fi
    ;;
  status)
    systemctl --user is-active "$WEB_UNIT" 2>/dev/null | sed 's/^/web: /' || true
    systemctl --user is-active "$BOT_UNIT" 2>/dev/null | sed 's/^/telegram: /' || true
    curl -fsS http://127.0.0.1:7861/api/local-model/status 2>/dev/null || echo 'local-model: unavailable'
    ;;
  logs)
    journalctl --user -u "$WEB_UNIT" -u "$BOT_UNIT" -n 100 --no-pager
    ;;
  public-start)
    reload_units
    systemctl --user enable --now "$TUNNEL_UNIT"
    echo "公网隧道正在建立；稍后运行：./manage.sh public-url"
    ;;
  public-stop)
    systemctl --user disable --now "$TUNNEL_UNIT" 2>/dev/null || true
    echo "公网隧道已停止"
    ;;
  public-restart)
    reload_units
    systemctl --user restart "$TUNNEL_UNIT"
    echo "公网隧道正在重新建立；稍后运行：./manage.sh public-url"
    ;;
  public-status)
    systemctl --user is-active "$TUNNEL_UNIT" 2>/dev/null | sed 's/^/tunnel: /' || true
    "$0" public-url
    ;;
  public-url)
    url="$(tail -n 200 "$TUNNEL_LOG" 2>/dev/null | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1 || true)"
    if [[ -n "$url" ]]; then echo "$url"; else echo "公网地址尚未生成"; fi
    ;;
  public-logs)
    journalctl --user -u "$TUNNEL_UNIT" -n 100 --no-pager
    ;;
  *) echo "Usage: $0 {start|stop|restart|status|logs|public-start|public-stop|public-restart|public-status|public-url|public-logs}"; exit 2 ;;
esac
