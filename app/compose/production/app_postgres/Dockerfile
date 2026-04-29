FROM python:3.13-slim-bullseye

RUN echo POSTGRES
ENV APP_ROOT /src
ENV CONFIG_ROOT /config
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ARG BUILD_ENVIRONMENT=production

RUN mkdir ${CONFIG_ROOT}
COPY app/requirements/base.txt ${CONFIG_ROOT}/base.txt
COPY app/requirements/${BUILD_ENVIRONMENT}.txt ${CONFIG_ROOT}/${BUILD_ENVIRONMENT}.txt

# Install gettext utilities for translations
RUN apt-get update && \
    apt-get install -y --no-install-recommends gettext-base gettext git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r ${CONFIG_ROOT}/${BUILD_ENVIRONMENT}.txt \
    && pip install gunicorn

WORKDIR ${APP_ROOT}


ADD app/ ${APP_ROOT}


COPY ./app/compose/production/app_postgres/start /start
#RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

COPY ./app/compose/production/app_postgres/celery/worker/start /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY ./app/compose/production/app_postgres/celery/beat/start /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./app/compose/production/app_postgres/celery/flower/start /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower


RUN adduser appuser --system --no-create-home --shell /bin/sh \
    && chown -R appuser ${APP_ROOT}

RUN chown appuser /start
RUN chown appuser /start-celeryworker
RUN chown appuser /start-celerybeat
RUN chown appuser /start-flower

USER appuser

CMD ${STARTUP_COMMAND}
