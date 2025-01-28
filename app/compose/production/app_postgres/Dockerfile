FROM python:3.9.5

RUN echo POSTGRES
ENV APP_ROOT /src
ENV CONFIG_ROOT /config
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir ${CONFIG_ROOT}
COPY requirements/base.txt ${CONFIG_ROOT}/base.txt
COPY requirements/production.txt ${CONFIG_ROOT}/production.txt


RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r ${CONFIG_ROOT}/production.txt

WORKDIR ${APP_ROOT}

ADD . ${APP_ROOT}

COPY ./djangoq_setup.sh /djangoq_setup.sh
RUN chmod +x /djangoq_setup.sh

RUN adduser appuser --system --no-create-home --shell /bin/sh \
    && chown -R appuser ${APP_ROOT}
USER appuser

CMD ${STARTUP_COMMAND}