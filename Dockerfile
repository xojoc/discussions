FROM python:3.11-slim

#RUN apk update && apk upgrade && \
#    apk add --no-cache make g++ bash git openssh postgresql-dev curl libffi-dev

RUN apt-get update \
   && apt-get upgrade -y \
   && apt-get install -y wget \
   && apt-get install -y less

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

ENV PYTHONUNBUFFERED 1
COPY ./requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /usr/src/app

EXPOSE 80

HEALTHCHECK --start-period=20s --interval=60s --timeout=60s --retries=3 CMD /usr/src/app/docker-healthcheck.sh

ENTRYPOINT ["/usr/src/app/docker-entrypoint.sh"]
