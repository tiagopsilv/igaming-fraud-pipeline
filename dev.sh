#!/usr/bin/env bash
# Dev orchestration for the iGaming fraud pipeline (Astro Runtime + Cosmos + dbt + BigQuery).
#
# One entry point for the local stack: it guarantees the dbt project is synced into airflow/include/
# (Cosmos reads it from there) BEFORE Airflow starts, so the DAG never imports broken.
#
# Usage:
#   ./dev.sh up        # sync + start Airflow, wait until healthy, print the URL
#   ./dev.sh rebuild   # sync + restart + trigger the pipeline (use after changing dbt models)
#   ./dev.sh trigger   # unpause + trigger the pipeline DAG
#   ./dev.sh sync      # copy the repo dbt/ + ingestion into airflow/include/ (mirror)
#   ./dev.sh status    # containers + DAG + last run state
#   ./dev.sh logs      # follow Airflow logs
#   ./dev.sh restart   # sync + astro dev restart
#   ./dev.sh down      # stop the stack
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIRFLOW_DIR="$REPO/airflow"
DAG_ID="igaming_fraud_pipeline"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m ok\033[0m %s\n' "$*"; }
err() { printf '\033[1;31merr\033[0m %s\n' "$*" >&2; }

require_docker() {
  if ! docker info >/dev/null 2>&1; then
    err "Docker não está rodando. Abra o Docker Desktop, espere ficar 'running', e rode de novo."
    exit 1
  fi
}

is_running() { docker ps --format '{{.Names}}' | grep -qi 'igaming.*webserver'; }

scheduler() { docker ps --format '{{.Names}}' | grep -i 'igaming.*scheduler' | head -1; }

web_url() {
  local port
  port="$(docker ps --filter 'name=webserver' --format '{{.Ports}}' \
          | grep -oE '[0-9]+->8080' | grep -oE '^[0-9]+' | head -1)"
  [ -n "$port" ] && echo "http://localhost:$port" || echo "http://localhost:8080"
}

sync_project() {
  log "Sincronizando dbt/ + ingestion para airflow/include/ (Cosmos lê de lá) ..."
  bash "$AIRFLOW_DIR/include/sync_project.sh"
  ok "sync concluído"
}

wait_healthy() {
  log "Esperando o Airflow subir ..."
  local sc
  for _ in $(seq 1 60); do
    sc="$(scheduler || true)"
    if [ -n "$sc" ] && docker exec "$sc" airflow dags list >/dev/null 2>&1; then
      ok "Airflow pronto"
      return 0
    fi
    sleep 3
  done
  err "Timeout esperando o Airflow ficar pronto."
  return 1
}

assert_dag_ok() {
  local sc; sc="$(scheduler)"
  local errors
  errors="$(docker exec "$sc" airflow dags list-import-errors 2>/dev/null | grep -c "$DAG_ID" || true)"
  if [ "${errors:-0}" != "0" ]; then
    err "O DAG tem import error. Rode: ./dev.sh sync   (include/dbt provavelmente está vazio)."
    docker exec "$sc" airflow dags list-import-errors 2>/dev/null | tail -20
    return 1
  fi
  ok "DAG '$DAG_ID' sem import errors"
}

cmd_up() {
  require_docker
  sync_project
  if is_running; then
    log "Stack já de pé; aplicando restart pra pegar o sync ..."
    ( cd "$AIRFLOW_DIR" && astro dev restart )
  else
    log "Subindo o Astro (astro dev start) ..."
    ( cd "$AIRFLOW_DIR" && astro dev start )
  fi
  wait_healthy
  assert_dag_ok
  ok "Airflow em $(web_url)   (login padrão do Astro: admin / admin)"
}

cmd_restart() {
  require_docker
  sync_project
  ( cd "$AIRFLOW_DIR" && astro dev restart )
  wait_healthy
  assert_dag_ok
  ok "Airflow em $(web_url)"
}

cmd_trigger() {
  require_docker
  local sc; sc="$(scheduler)"
  [ -n "$sc" ] || { err "Airflow não está de pé. Rode ./dev.sh up primeiro."; exit 1; }
  assert_dag_ok
  docker exec "$sc" airflow dags unpause "$DAG_ID" >/dev/null 2>&1 || true
  log "Disparando o pipeline ..."
  docker exec "$sc" airflow dags trigger "$DAG_ID" >/dev/null
  ok "Pipeline disparado. Acompanhe em $(web_url) (aba Grid) ou: ./dev.sh status"
}

cmd_rebuild() {
  cmd_restart
  cmd_trigger
}

cmd_status() {
  require_docker
  log "Containers:"
  docker ps --filter 'name=igaming' --format '  {{.Names}}\t{{.Status}}\t{{.Ports}}'
  local sc; sc="$(scheduler || true)"
  if [ -n "$sc" ]; then
    echo ""
    log "Última execução do DAG:"
    docker exec "$sc" airflow dags list-runs -d "$DAG_ID" 2>/dev/null | head -5
    echo ""
    ok "URL: $(web_url)"
  else
    err "Stack não está rodando. Rode ./dev.sh up"
  fi
}

cmd_logs() { ( cd "$AIRFLOW_DIR" && astro dev logs -f ); }

cmd_down() {
  require_docker
  ( cd "$AIRFLOW_DIR" && astro dev stop )
  ok "Stack parado (dados no volume preservados). Use ./dev.sh up pra subir de novo."
}

case "${1:-}" in
  up)       cmd_up ;;
  rebuild)  cmd_rebuild ;;
  trigger)  cmd_trigger ;;
  sync)     sync_project ;;
  restart)  cmd_restart ;;
  status)   cmd_status ;;
  logs)     cmd_logs ;;
  down)     cmd_down ;;
  *)
    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
    exit 1 ;;
esac
