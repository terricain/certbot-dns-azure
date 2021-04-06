certbot-dns-azure
=================

[![Tests](https://github.com/binkhq/certbot-dns-azure/workflows/Release/badge.svg)](https://github.com/binkhq/certbot-dns-azure/actions)
[![Python Version](https://img.shields.io/pypi/pyversions/certbot-dns-azure)](https://pypi.org/project/certbot-dns-azure/)
[![PyPi Status](https://img.shields.io/pypi/status/certbot-dns-azure)](https://pypi.org/project/certbot-dns-azure/)
[![Version](https://img.shields.io/pypi/v/certbot-dns-azure)](https://pypi.org/project/certbot-dns-azure/)
[![Docs](https://readthedocs.org/projects/certbot-dns-azure/badge/?version=latest&style=flat)](https://certbot-dns-azure.readthedocs.io/en/latest/)

AzureDNS Authenticator plugin for [Certbot](https://certbot.eff.org/).

This plugin is built from the ground up and follows the development style and life-cycle
of other `certbot-dns-*` plugins found in the
[Official Certbot Repository](https://github.com/certbot/certbot). PR is open [here](https://github.com/certbot/certbot/pull/8727) though Certbot is not accepting plugin PR's at the moment.

Installation
------------

```
pip install certbot certbot-dns-azure
```

Verify:

```
$ certbot plugins --text

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
* dns-azure
Description: Obtain certificates using a DNS TXT record (if you are using Azure
for DNS).
Interfaces: IAuthenticator, IPlugin
Entry point: dns-azure = certbot_dns_azure.dns_azure:Authenticator

...
...
```

Docs and instructions on configuration are [here](https://certbot-dns-azure.readthedocs.io/en/latest/)


