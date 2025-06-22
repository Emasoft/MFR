#!/bin/bash
# Wrapper script for yamlfmt to handle different installation paths

# Check common installation locations
if command -v yamlfmt &> /dev/null; then
    # yamlfmt is in PATH
    exec yamlfmt "$@"
elif [ -x "$HOME/go/bin/yamlfmt" ]; then
    # yamlfmt in user's go/bin
    exec "$HOME/go/bin/yamlfmt" "$@"
elif [ -x "/usr/local/go/bin/yamlfmt" ]; then
    # yamlfmt in system go/bin
    exec "/usr/local/go/bin/yamlfmt" "$@"
else
    echo "Error: yamlfmt not found. Install with: go install github.com/google/yamlfmt/cmd/yamlfmt@latest" >&2
    echo "Make sure ~/go/bin is in your PATH" >&2
    exit 1
fi
