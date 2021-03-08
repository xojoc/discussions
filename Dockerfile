FROM python:3.9.2-alpine

RUN apk update && apk upgrade && \
    apk add --no-cache make g++ bash git openssh postgresql-dev curl

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /usr/src/app
COPY ./docker-healthcheck.sh /usr/src/app

EXPOSE 80

HEALTHCHECK --start-period=30s --interval=10s --timeout=10s --retries=3 CMD /usr/src/app/docker-healthcheck.sh


CMD ["/usr/src/app/docker-entrypoint.sh"]
