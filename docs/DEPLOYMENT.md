# Deployment

## Source Of Truth

GitHub is the source of truth for Shorts Factory Backend code.

Runtime secrets stay on the VPS and must not be committed, copied into logs, or
stored in GitHub. The deploy flow updates only the `shorts-factory-backend`
container.

## Production Paths

- App root: `/opt/shorts-factory-backend`
- Git checkout: `/opt/shorts-factory-backend/repo`
- Releases: `/opt/shorts-factory-backend/releases/<commit>`
- Persistent data: `/opt/shorts-factory-backend/data`
- Runtime env: `/etc/shorts-factory-backend/runtime.env`
- Container: `shorts-factory-backend`
- Image tag format: `shorts-factory-backend:<commit_short>`

Do not delete `/opt/shorts-factory-backend/data`, existing release folders, or
`/etc/shorts-factory-backend/runtime.env` during a deploy.

## Initial VPS Checkout

Clone the GitHub repository once:

```bash
sudo install -d /opt/shorts-factory-backend
sudo git clone <GITHUB_REPO_URL> /opt/shorts-factory-backend/repo
```

The runtime env file must already exist on the VPS:

```bash
test -f /etc/shorts-factory-backend/runtime.env
```

Do not paste secret values into the repository or terminal output.

## Safe Manual Deploy

Run the deploy script from the VPS checkout:

```bash
cd /opt/shorts-factory-backend/repo
bash scripts/deploy_vps_shorts_factory.sh main
```

For a feature branch or exact commit:

```bash
bash scripts/deploy_vps_shorts_factory.sh feat/local-e2e-render
bash scripts/deploy_vps_shorts_factory.sh 18f844b372fca425c9b4b922ab936661785a568f
```

The script:

- fetches GitHub code;
- resolves the deploy commit;
- creates `/opt/shorts-factory-backend/releases/<commit>`;
- builds `shorts-factory-backend:<commit_short>`;
- stops and removes only the existing `shorts-factory-backend` container;
- starts only `shorts-factory-backend`;
- mounts `/opt/shorts-factory-backend/data:/data`;
- uses `/etc/shorts-factory-backend/runtime.env`;
- checks `/health`, `/ready`, DB access, and production template invariants.

It does not run `docker compose down`, does not prune Docker resources, and does
not touch other containers or other `/opt/*` applications.

## Runtime Verification

After deploy, verify:

```bash
curl -fsS http://127.0.0.1:8020/health
curl -fsS http://127.0.0.1:8020/ready

docker exec shorts-factory-backend python - <<'PY'
from pathlib import Path
import inspect

from shorts_factory.generation.image_generator import OpenAIImageGenerator
from shorts_factory.generation.schemas import PRODUCTION_FRAME_SEQUENCE
from shorts_factory.rendering.production_templates import PRODUCTION_TEMPLATES
from shorts_factory.settings import Settings

source = inspect.getsource(OpenAIImageGenerator.generate)
print("production_templates_exists", Path("/app/shorts_factory/rendering/production_templates.py").exists())
print("production_template_count", len(PRODUCTION_TEMPLATES))
print("openai_image_size", Settings().openai_image_size)
print("hardcoded_1024x1792_present", "1024x1792" in source)
print("production_order", " -> ".join(frame.value for frame in PRODUCTION_FRAME_SEQUENCE))
PY
```

Also verify no publishing happened during deploy:

```bash
docker exec shorts-factory-backend python - <<'PY'
from sqlalchemy import func, select

from shorts_factory.db.models import PublishLog, VideoJob
from shorts_factory.db.session import create_session_factory, get_engine
from shorts_factory.settings import Settings

settings = Settings()
engine = get_engine(settings)
Session = create_session_factory(engine)
session = Session()
try:
    print("video_job_count", session.scalar(select(func.count()).select_from(VideoJob)))
    print("publish_logs_total", session.scalar(select(func.count()).select_from(PublishLog)))
finally:
    session.close()
    engine.dispose()
PY
```

## Manual Rollback

List existing images and releases:

```bash
docker images "shorts-factory-backend"
ls -1 /opt/shorts-factory-backend/releases
```

Restart the previous image, replacing only the Shorts Factory Backend container:

```bash
PREVIOUS_TAG=shorts-factory-backend:<previous_commit_short>

docker stop shorts-factory-backend
docker rm shorts-factory-backend
docker run -d \
  --name shorts-factory-backend \
  --restart unless-stopped \
  --env-file /etc/shorts-factory-backend/runtime.env \
  -p 127.0.0.1:8020:8000 \
  -v /opt/shorts-factory-backend/data:/data \
  "$PREVIOUS_TAG"

curl -fsS http://127.0.0.1:8020/health
curl -fsS http://127.0.0.1:8020/ready
```

Rollback must not delete data, media, runtime env files, or release folders.
