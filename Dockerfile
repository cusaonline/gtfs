FROM python/python:3.14-alpine AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD src/ /gtfs/src
ADD .python-version /gtfs
ADD pyproject.toml /gtfs

RUN apk update
RUN apk --no-cache upgrade
RUN uv sync

FROM base AS final

ENTRYPOINT [ "python", "/gtfs/__main__.py" ]
