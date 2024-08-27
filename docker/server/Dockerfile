# Build with
#   docker build -t <imagename> .
#
# where for Rob on spin, <imagename> = registry.nersc.gov/m4385/raknop/roman-desc-simdex-server

FROM rknop/devuan-daedalus-rknop AS base
LABEL maintainer="Rob Knop <raknop@lbl.gov>"

SHELL ["/bin/bash", "-c"]

RUN mkdir -p /flask
WORKDIR /flask

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="UTC"

RUN  apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install -y \
         python3 tmux netcat-openbsd curl elinks postgresql-client make \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python
ENV LESS=-XLRi

# ======================================================================
FROM base AS build

RUN DEBIAN_FRONTEND="noninteractive" TZ="US/Pacific" \
    apt-get update \
    && DEBIAN_FRONTEND="noninteractive" TZ="US/Pacific" \
    apt-get -y install -y python3-pip python3-venv git libpq-dev

RUN mkdir /venv
RUN python3 -mvenv /venv

RUN source /venv/bin/activate && \
    pip --no-cache install \
       flask \
       gunicorn \
       psycopg2 \
       python-dateutil \
       pytz \
       requests \
       astropy

# ======================================================================
FROM base AS webserver

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

RUN mkdir /sessions

ENTRYPOINT [ "gunicorn", "-w", "1", "--threads", "10", "-b", "0.0.0.0:8080", "--timeout", "0", "server:app" ]
