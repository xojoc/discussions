FROM python:3.9.2-alpine

RUN apk update && apk upgrade && \
    apk add --no-cache make g++ bash git openssh postgresql-dev curl

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

#COPY ./.env /usr/src/app/

COPY ./requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /usr/src/app

EXPOSE 80

#RUN python manage.py migrate
#CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]
CMD ["/usr/src/app/docker-entrypoint.sh"]