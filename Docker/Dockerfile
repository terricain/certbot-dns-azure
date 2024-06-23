FROM python:alpine

RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python

ARG TARGETARCH
RUN if [ $TARGETARCH = "arm64" ]; then \
        apk add --update --no-cache gcc musl-dev libffi-dev \
        ; fi

RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools certbot certbot-dns-azure
