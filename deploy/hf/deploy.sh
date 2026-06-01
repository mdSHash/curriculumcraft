#!/usr/bin/env bash
# Deploy the CurriculumCraft backend to Hugging Face Spaces.
#
# Prerequisites:
#   - HF_TOKEN  exported   (write-access token from https://huggingface.co/settings/tokens)
#   - HF_USER   exported   (your HF username)
#   - HF_SPACE  optional   (Space repo name; defaults to "curriculumcraft")
#
# Usage:
#   HF_TOKEN=hf_xxx HF_USER=yourname ./deploy/hf/deploy.sh
#
# What it does:
#   1. Creates the Space if it doesn't exist (Docker SDK, public).
#   2. Builds a clean staging dir = backend/ + the HF overlay (Dockerfile, README, .gitattributes).
#   3. Pushes that staging dir to the Space's git repo.
#
# The first push triggers a Docker build on HF that takes ~10-20 minutes
# (downloads pytorch + sentence-transformers + faiss). Subsequent pushes
# are much faster thanks to layer caching.

set -euo pipefail

if [[ -z "${HF_TOKEN:-}" || -z "${HF_USER:-}" ]]; then
    echo "Usage: HF_TOKEN=hf_xxx HF_USER=yourname $0" >&2
    exit 1
fi

HF_SPACE="${HF_SPACE:-curriculumcraft}"
REPO_ID="${HF_USER}/${HF_SPACE}"
SPACE_URL="https://huggingface.co/spaces/${REPO_ID}"
GIT_URL="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${REPO_ID}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OVERLAY_DIR="${REPO_ROOT}/deploy/hf"
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT

echo "→ Repo:       ${REPO_ID}"
echo "→ Staging:    ${STAGING_DIR}"

# 1. Create Space if missing.
echo "→ Ensuring Space exists..."
curl -sS -X POST "https://huggingface.co/api/repos/create" \
    -H "Authorization: Bearer ${HF_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"type\":\"space\",\"name\":\"${HF_SPACE}\",\"organization\":null,\"private\":false,\"sdk\":\"docker\"}" \
    | tee "${STAGING_DIR}/.create-response.json" >/dev/null
if grep -q "already" "${STAGING_DIR}/.create-response.json" 2>/dev/null; then
    echo "  (already exists, ok)"
fi
rm -f "${STAGING_DIR}/.create-response.json"

# 2. Build staging directory.
echo "→ Assembling files..."
cp -r "${REPO_ROOT}/backend/"* "${STAGING_DIR}/"
# Strip local-only artifacts.
rm -rf "${STAGING_DIR}/venv" "${STAGING_DIR}/__pycache__" \
       "${STAGING_DIR}/data" "${STAGING_DIR}/.pytest_cache"
find "${STAGING_DIR}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
# Don't ship the local .env — secrets come from HF Space secrets.
rm -f "${STAGING_DIR}/.env"
# Overlay HF-specific files (Dockerfile replaces backend's, README + .gitattributes are new).
cp "${OVERLAY_DIR}/Dockerfile"     "${STAGING_DIR}/Dockerfile"
cp "${OVERLAY_DIR}/README.md"      "${STAGING_DIR}/README.md"
cp "${OVERLAY_DIR}/.gitattributes" "${STAGING_DIR}/.gitattributes"

# 3. Init git, push.
echo "→ Pushing to HF..."
cd "${STAGING_DIR}"
git init -q -b main
git config user.email "${HF_USER}@users.noreply.huggingface.co"
git config user.name  "${HF_USER}"
git add .
git commit -q -m "Deploy CurriculumCraft backend"
git remote add origin "${GIT_URL}"
if ! git push -f origin main; then
    echo
    echo "Push to HF Space FAILED. Scroll up for the upstream error from huggingface.co -- typically a YAML metadata rejection in deploy/hf/README.md (e.g. short_description over 60 chars). Fix the issue and re-run." >&2
    exit 1
fi

echo
echo "✓ Pushed. Build will start automatically."
echo "  Watch logs:    ${SPACE_URL}"
echo "  Health (when ready):  https://${HF_USER}-${HF_SPACE}.hf.space/api/health"
