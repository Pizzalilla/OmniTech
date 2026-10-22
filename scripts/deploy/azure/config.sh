# Shared settings for the Azure deployment scripts. Override any value with an environment variable.
AZ_LOCATION="${AZ_LOCATION:-australiaeast}"
AZ_RG="${AZ_RG:-omnitech-rg}"
AZ_ENV="${AZ_ENV:-omnitech-env}"
# Commit hash; uncommitted changes get a timestamp so Azure always rolls out a new revision.
if [[ -z "${IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="$(git rev-parse --short HEAD)"
  [[ -z "$(git status --porcelain)" ]] || IMAGE_TAG="$IMAGE_TAG-dirty-$(date +%Y%m%d%H%M%S)"
fi

# name | build context | Dockerfile | container port
SERVICES=(
  "home|.|scripts/deploy/azure/home/Dockerfile|80"
  "student-1|student-1|student-1/Dockerfile|5000"
  "student-2|student-2|student-2/Dockerfile|5000"
  "student-3|student-3|student-3/Dockerfile|5000"
  "student-4|student-4|student-4/Dockerfile|5004"
  "student-5|student-5|student-5/Dockerfile|5000"
)

# Cloud baseline: AI-Mode, MCP, RAG and the Multi-Agent Server are disabled by default.
# ".invalid" never resolves (RFC 2606), so any AI call fails immediately instead of hanging.
DISABLED_AI="http://ai-disabled.invalid"
AI_DISABLED_ENV=(
  "AI_MODE_ENABLED=false"
  "AI_ENABLED=false"
  "RAG_ENABLED=false"
  "MCP_ENABLED=false"
  "MULTI_AGENT_ENABLED=false"
  "OLLAMA_HOST=${DISABLED_AI}:11434"
  "OLLAMA_BASE_URL=${DISABLED_AI}:11434/v1"
  "RAG_HOST=${DISABLED_AI}:6002"
  "RAG_SERVER_URL=${DISABLED_AI}:6002"
  "MCP_HOST=${DISABLED_AI}:6003"
  "MCP_SERVER_URL=${DISABLED_AI}:6003"
  "MULTI_AGENT_HOST=${DISABLED_AI}:6004"
  "FLASK_DEBUG=0"
)
