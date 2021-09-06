FROM python:rc-alpine3.12

COPY ./rtlamr2mqtt.py /usr/bin
COPY ./requirements.txt /tmp

WORKDIR /tmp
RUN apk update \
    && apk add rtl-sdr \
    && pip3 install -r /tmp/requirements.txt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py \
    && apk add go \
    && apk add git \
    && export GOPATH=/tmp \
    && go get github.com/bemasher/rtlamr \
    && cp /tmp/bin/rtlamr /usr/bin/rtlamr \
    && chmod 755 /usr/bin/rtlamr

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]
