FROM python:3.9.5

RUN echo POSTGRES
ENV APP_ROOT /src
ENV CONFIG_ROOT /config
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir ${CONFIG_ROOT}
COPY app/requirements/base.txt ${CONFIG_ROOT}/base.txt
COPY app/requirements/production.txt ${CONFIG_ROOT}/production.txt


RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r ${CONFIG_ROOT}/production.txt

WORKDIR ${APP_ROOT}

ADD app/ ${APP_ROOT}

COPY ./app/djangoq_setup.sh /djangoq_setup.sh
RUN chmod +x /djangoq_setup.sh

COPY ./app/compose/production/app_postgres/start /start
#RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

RUN adduser appuser --system --no-create-home --shell /bin/sh \
    && chown -R appuser ${APP_ROOT}

RUN chown appuser /start
RUN chown appuser /djangoq_setup.sh

USER appuser



CMD ${STARTUP_COMMAND}