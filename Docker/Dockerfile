FROM alpine:latest

RUN apk add --update --no-cache python3 py3-pip && ln -sf python3 /usr/bin/python
RUN pip3 install --no-cache --break-system-packages certbot certbot-dns-azure