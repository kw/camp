FROM python:3.13-slim-bullseye

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY . .

RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install -n --no-cache --no-root
RUN python manage.py collectstatic --no-input
