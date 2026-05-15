#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="shorts-factory-backend"
IMAGE_NAME="shorts-factory-backend"
APP_ROOT="/opt/shorts-factory-backend"
REPO_DIR="${APP_ROOT}/repo"
RELEASES_DIR="${APP_ROOT}/releases"
DATA_DIR="${APP_ROOT}/data"
RUNTIME_ENV="/etc/shorts-factory-backend/runtime.env"
HOST_BIND="127.0.0.1:8020:8000"
DEPLOY_REF="${1:-main}"

if [[ "${SERVICE_NAME}" != "shorts-factory-backend" ]]; then
  echo "Refusing to deploy unexpected service: ${SERVICE_NAME}" >&2
  exit 1
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_path() {
  local path="$1"
  local description="$2"
  if [[ ! -e "${path}" ]]; then
    echo "Missing ${description}: ${path}" >&2
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  local name="$2"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null; then
      echo "${name}=ok"
      return 0
    fi
    sleep 1
  done
  echo "${name}=failed" >&2
  return 1
}

resolve_ref() {
  local ref="$1"
  git fetch --prune origin
  if git rev-parse --verify --quiet "origin/${ref}^{commit}" >/dev/null; then
    git checkout -B "${ref}" "origin/${ref}"
    git pull --ff-only origin "${ref}"
  elif git rev-parse --verify --quiet "${ref}^{commit}" >/dev/null; then
    git checkout --detach "${ref}"
  else
    echo "Cannot resolve deploy ref: ${ref}" >&2
    exit 1
  fi
  git rev-parse HEAD
}

runtime_verify() {
  docker exec "${SERVICE_NAME}" python - <<'PY'
from pathlib import Path
import inspect

from sqlalchemy import text

from shorts_factory.db.session import create_session_factory, get_engine
from shorts_factory.generation.image_generator import OpenAIImageGenerator
from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE
from shorts_factory.rendering.production_templates import (
    PRODUCTION_TEMPLATES,
    validate_production_frame_order,
)
from shorts_factory.settings import Settings

settings = Settings()
source = inspect.getsource(OpenAIImageGenerator.generate)
order = tuple(frame.value for frame in PRODUCTION_FRAME_SEQUENCE)
validate_production_frame_order(PRODUCTION_FRAME_SEQUENCE)
production_templates_path = Path("/app/shorts_factory/rendering/production_templates.py")
hardcoded_paths = [
    path
    for path in Path("/app/shorts_factory").rglob("*.py")
    if "1024x1792" in path.read_text(encoding="utf-8")
]

if not production_templates_path.exists():
    raise RuntimeError("production_templates.py is missing in the running container.")
if settings.openai_image_size != "1024x1536":
    raise RuntimeError(f"Unexpected OpenAI image size: {settings.openai_image_size}")
if "self._settings.openai_image_size" not in source:
    raise RuntimeError("OpenAIImageGenerator does not use settings.openai_image_size.")
if hardcoded_paths:
    joined = ", ".join(str(path) for path in hardcoded_paths)
    raise RuntimeError(f"Hardcoded 1024x1792 remains in runtime code: {joined}")
if order != ("hook", "question", "options", "pause", "answer", "cta"):
    raise RuntimeError(f"Unexpected production frame order: {order}")

engine = get_engine(settings)
if engine is None:
    raise RuntimeError("Database engine is not configured.")
Session = create_session_factory(engine)
session = Session()
try:
    db_value = session.execute(text("select 1")).scalar_one()
finally:
    session.close()
    engine.dispose()

print("db_select_1", db_value)
print("production_templates_exists", production_templates_path.exists())
print("production_template_count", len(PRODUCTION_TEMPLATES))
print("openai_image_size", settings.openai_image_size)
print("image_generator_uses_settings_openai_image_size", "self._settings.openai_image_size" in source)
print("hardcoded_1024x1792_present", bool(hardcoded_paths))
print("production_order", " -> ".join(order))
print("production_order_enforced", order == ("hook", "question", "options", "pause", "answer", "cta"))
PY
}

rollback() {
  local old_image="$1"
  if [[ -z "${old_image}" ]]; then
    echo "No previous image recorded; manual intervention required." >&2
    return 1
  fi
  echo "Rolling back ${SERVICE_NAME} to ${old_image}" >&2
  docker rm -f "${SERVICE_NAME}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${SERVICE_NAME}" \
    --restart unless-stopped \
    --env-file "${RUNTIME_ENV}" \
    -p "${HOST_BIND}" \
    -v "${DATA_DIR}:/data" \
    "${old_image}" >/dev/null
}

main() {
  require_command git
  require_command docker
  require_command curl
  require_path "${REPO_DIR}/.git" "Git checkout"
  require_path "${RUNTIME_ENV}" "runtime env file"

  mkdir -p "${RELEASES_DIR}" "${DATA_DIR}"

  cd "${REPO_DIR}"
  local commit
  commit="$(resolve_ref "${DEPLOY_REF}")"
  local commit_short
  commit_short="$(git rev-parse --short=12 "${commit}")"
  local release_dir="${RELEASES_DIR}/${commit}"
  local image_tag="${IMAGE_NAME}:${commit_short}"
  local old_image
  old_image="$(docker inspect --format '{{.Config.Image}}' "${SERVICE_NAME}" 2>/dev/null || true)"

  if [[ ! -d "${release_dir}" ]]; then
    mkdir -p "${release_dir}"
    git archive "${commit}" | tar -xf - -C "${release_dir}"
    printf "%s\n" "${commit}" > "${release_dir}/.deployed_commit"
  fi

  docker build -t "${image_tag}" "${release_dir}"

  local old_container_id
  old_container_id="$(docker ps -aq --filter "name=^/${SERVICE_NAME}$")"
  if [[ -n "${old_container_id}" ]]; then
    docker stop "${old_container_id}" >/dev/null
    docker rm "${old_container_id}" >/dev/null
  fi

  local new_container_id
  new_container_id="$(
    docker run -d \
      --name "${SERVICE_NAME}" \
      --restart unless-stopped \
      --env-file "${RUNTIME_ENV}" \
      -p "${HOST_BIND}" \
      -v "${DATA_DIR}:/data" \
      "${image_tag}"
  )"

  if ! wait_for_http "http://127.0.0.1:8020/health" "health"; then
    rollback "${old_image}"
    exit 1
  fi
  if ! wait_for_http "http://127.0.0.1:8020/ready" "ready"; then
    rollback "${old_image}"
    exit 1
  fi

  if ! runtime_verify; then
    rollback "${old_image}"
    exit 1
  fi

  echo "deployed_commit=${commit}"
  echo "docker_image=${image_tag}"
  echo "container_id=${new_container_id}"
}

main "$@"
