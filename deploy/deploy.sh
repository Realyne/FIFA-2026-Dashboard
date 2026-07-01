#!/usr/bin/env bash
# Deploy the World Cup 2026 dashboard to realyne-cloud.
#
# Static SPA is served by Nginx from /var/www/wc2026-dashboard/www.
# The data API runs in Docker on 127.0.0.1:8100; Nginx proxies /api/wc/.
#
# Usage:
#   ./deploy/deploy.sh              # deploy to realyne-cloud (default)
#   ./deploy/deploy.sh --ssl        # obtain TLS cert via certbot, then redeploy
#
# Env overrides:
#   HOST         SSH host alias          (default: realyne-cloud)
#   REMOTE_DIR   remote app directory    (default: wc2026-dashboard)
#   DOMAIN       public hostname          (default: wc2026.realyne.com)
#   API_PORT     localhost API bind port  (default: 8100)

set -euo pipefail

HOST="${HOST:-realyne-cloud}"
REMOTE_DIR="${REMOTE_DIR:-wc2026-dashboard}"
WEB_ROOT="${WEB_ROOT:-/var/www/wc2026-dashboard/www}"
DOMAIN="${DOMAIN:-wc2026.realyne.com}"
API_PORT="${API_PORT:-8100}"
SETUP_SSL=0

for arg in "$@"; do
  case "$arg" in
    --ssl) SETUP_SSL=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"
remote_home="$(ssh "$HOST" 'printf %s "$HOME"')"
remote_root="${remote_home}/${REMOTE_DIR}"

substitute() {
  sed \
    -e "s|__DOMAIN__|${DOMAIN}|g" \
    -e "s|__API_PORT__|${API_PORT}|g" \
    -e "s|__WEB_ROOT__|${WEB_ROOT}|g"
}

echo "==> Syncing SPA to ${HOST}:${WEB_ROOT}"
ssh "$HOST" "mkdir -p '${REMOTE_DIR}/www-staging'"
rsync -az --delete \
  "${root}/index.html" \
  "${root}/styles.css" \
  "${root}/data.js" \
  "${root}/app.jsx" \
  "${root}/ui.jsx" \
  "${root}/landing.jsx" \
  "${root}/groups.jsx" \
  "${root}/bracket.jsx" \
  "${root}/matchdetail.jsx" \
  "${root}/players.jsx" \
  "${root}/playerdetail.jsx" \
  "${root}/search.jsx" \
  "${HOST}:${REMOTE_DIR}/www-staging/"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
sudo mkdir -p '${WEB_ROOT}'
sudo rsync -a --delete '${remote_root}/www-staging/' '${WEB_ROOT}/'
sudo chown -R www-data:www-data '/var/www/wc2026-dashboard'
EOF

echo "==> Syncing wc2026-data-service to ${HOST}:${REMOTE_DIR}/wc2026-data-service"
ssh "$HOST" "mkdir -p '${REMOTE_DIR}/wc2026-data-service'"
rsync -az --delete \
  --exclude .venv \
  --exclude .pytest_cache \
  --exclude __pycache__ \
  --exclude '*.pyc' \
  --exclude .env \
  --exclude .playwright-cli \
  --exclude 'debug/*.json' \
  "${root}/wc2026-data-service/" \
  "${HOST}:${REMOTE_DIR}/wc2026-data-service/"

echo "==> Syncing deploy compose file"
scp -q "${here}/docker-compose.prod.yml" "${HOST}:${REMOTE_DIR}/docker-compose.prod.yml"

echo "==> Building and starting API on ${HOST} (127.0.0.1:${API_PORT})"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
cd '${REMOTE_DIR}'
export API_PORT='${API_PORT}'
# ubuntu is not in the docker group on this host — sudo is required.
# The 6.8GB root disk fills after a few rebuilds. -f only prunes
# *dangling* (untagged) images; the previous api build can linger as a
# tagged image and never get reclaimed (1.2GB seen in the wild). -a
# prunes every image not used by a running container, so the old build
# is always cleared. The pre-build pass keeps the running image (still
# in use); the post-build pass drops it once the new container is up.
sudo docker image prune -af >/dev/null
sudo docker builder prune -f >/dev/null
sudo docker compose -f docker-compose.prod.yml up --build -d
sudo docker image prune -af >/dev/null
sudo docker compose -f docker-compose.prod.yml ps
df -h / | tail -1
EOF

if [[ "${SETUP_SSL}" -eq 1 ]]; then
  echo "==> Obtaining TLS certificate for ${DOMAIN} (DNS must point at this host)"
  ssh -t "$HOST" "sudo certbot certonly --nginx -d '${DOMAIN}'"
fi

echo "==> Installing Nginx site for ${DOMAIN}"
nginx_tmp="$(mktemp)"
if ssh "$HOST" "sudo test -f /etc/letsencrypt/live/${DOMAIN}/fullchain.pem"; then
  echo "    TLS certs found — HTTP redirect + HTTPS"
  {
    substitute < "${here}/nginx-wc2026-http-redirect.conf"
    echo ""
    substitute < "${here}/nginx-wc2026-ssl.conf"
  } > "${nginx_tmp}"
else
  echo "    No TLS certs — serving HTTP only (point DNS, then run with --ssl)"
  substitute < "${here}/nginx-wc2026.conf" > "${nginx_tmp}"
fi

scp -q "${nginx_tmp}" "${HOST}:/tmp/wc2026-nginx.conf"
rm -f "${nginx_tmp}"

ssh "$HOST" bash -s <<'EOF'
set -euo pipefail
sudo cp /tmp/wc2026-nginx.conf /etc/nginx/sites-available/wc2026
sudo ln -sf /etc/nginx/sites-available/wc2026 /etc/nginx/sites-enabled/wc2026
sudo nginx -t
sudo systemctl reload nginx
rm -f /tmp/wc2026-nginx.conf
EOF

echo ""
echo "Deployed to ${HOST}"
echo "  SPA root : ${WEB_ROOT}"
echo "  API      : 127.0.0.1:${API_PORT}  (proxied at /api/wc/)"
if ssh "$HOST" "sudo test -f /etc/letsencrypt/live/${DOMAIN}/fullchain.pem" 2>/dev/null; then
  echo "  URL      : https://${DOMAIN}"
else
  echo "  URL      : http://${DOMAIN}  (add DNS A record, then ./deploy/deploy.sh --ssl)"
fi
echo ""
echo "Health: ssh ${HOST} 'curl -s http://127.0.0.1:${API_PORT}/healthz'"
