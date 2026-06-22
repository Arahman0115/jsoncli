# Optional containerized build of jsoncli.
#
# Build:   docker build -t jsoncli /Users/afroza/jsoncli
# Run:     docker run --rm -it -v "$PWD":/data jsoncli /data/sample.json
#
# The -it flags are REQUIRED: the viewer is interactive and needs a TTY.
# Mount the directory holding your JSON with -v so the container can read it.

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY jsoncli ./jsoncli
RUN pip install --no-cache-dir .

# A sensible default term so colors render in the container.
ENV TERM=xterm-256color

WORKDIR /data
ENTRYPOINT ["jsoncli"]
