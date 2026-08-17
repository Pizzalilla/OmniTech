#!/usr/bin/env bash
# Pull a model into the running Ollama container.
# Usage: ./pull-model.sh [model-name]
# Defaults to llama3.2 if no argument is given.

MODEL="${1:-llama3.2}"
echo "Pulling model: $MODEL"
curl -s http://localhost:11434/api/pull -d "{\"name\": \"$MODEL\"}" | while read -r line; do
  echo "$line"
done
echo "Done."
