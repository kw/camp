FROM python:3.14-slim-bullseye

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY . .

RUN pip install uv
RUN poetry config virtualenvs.create false
RUN uv sync
RUN uv run python manage.py collectstatic --no-input
