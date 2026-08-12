#!/usr/bin/env bash
set -euo pipefail

QUARTO_VERSION="1.9.37"

wget -qO- "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" | tar -xz -C /tmp
export PATH="$PATH:/tmp/quarto-${QUARTO_VERSION}/bin"

if [ "$CONTEXT" = "production" ]; then
  # `quarto install tinytex` picks a random CTAN mirror; retry since an
  # individual mirror can be temporarily out of sync and fail the install.
  for attempt in 1 2 3; do
    if quarto install tinytex --no-prompt; then
      break
    fi
    if [ "$attempt" = "3" ]; then
      echo "quarto install tinytex failed after 3 attempts" >&2
      exit 1
    fi
    sleep 10
  done

  quarto install chrome-headless-shell --no-prompt
  quarto render
else
  quarto render --to html
fi
