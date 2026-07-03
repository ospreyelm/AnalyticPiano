ARG PYTHON_VERSION=3.12-slim
ARG NODE_VERSION=22-slim

FROM node:${NODE_VERSION} AS frontend-build

WORKDIR /code

COPY package.json package-lock.json /code/
RUN npm ci
COPY . /code
RUN npm run build

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies.
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /code

WORKDIR /code

RUN pip install pipenv
COPY Pipfile Pipfile.lock /code/
RUN pipenv install --deploy --system
COPY . /code
COPY --from=frontend-build /code/lab/static/dist /code/lab/static/dist

RUN DJANGO_SETTINGS_MODULE=harmony.settings.fly \
    SECRET_KEY=build-placeholder \
    DATABASE_URL=sqlite:///tmp/build.db \
    python manage.py collectstatic --noinput

EXPOSE 8000


CMD ["gunicorn","--bind",":8000","--workers","1","--timeout","300","--graceful-timeout","300","harmony.wsgi:application"]
