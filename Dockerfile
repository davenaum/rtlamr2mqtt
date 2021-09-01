FROM python:rc-alpine3.12

COPY ./rtlamr2mqtt.py /usr/bin
COPY ./requirements.txt /tmp

WORKDIR /tmp
RUN apk update \
    && apk add rtl-sdr \
    && pip3 install -r /tmp/requirements.txt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py \
    && wget https://github.com/bemasher/rtlamr/releases/download/v0.9.1/rtlamr_linux_amd64.tar.gz \
    && tar zxvf rtlamr_linux_amd64.tar.gz \
    && chmod 755 rtlamr \
    && mv rtlamr /usr/bin \
    && rm -f /tmp/*

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]
