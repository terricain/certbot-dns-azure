"""
The `~certbot_dns_azure.dns_azure` plugin automates the process of
completing a ``dns-01`` challenge (`~acme.challenges.DNS01`) by creating, and
subsequently removing, TXT records using the Azure API.

.. note::
   The plugin is not installed by default. It can be installed by heading to
   `certbot.eff.org <https://certbot.eff.org/instructions#wildcard>`_, choosing your system and
   selecting the Wildcard tab.

Named Arguments
---------------

========================================  =====================================
``--dns-azure-config``                    Azure config INI file.
                                          (Required)
``--dns-azure-credentials``               Alias for --dns-azure-config
========================================  =====================================


Configuration
-------------

Use of this plugin requires a configuration file containing Azure API
credentials or information.

This plugin supported API authentication using either Service Principals or
utilising a Managed Identity assigned to the virtual machine.

Regardless which authentication method used, the identity will need the
"DNS Zone Contributor" role assigned to it.

As multiple Azure DNS Zones in multiple resource groups can exist, the config
file needs a mapping of zone to resource group ID. Multiple zones -> ID mappings
can be listed by using the key ``dns_azure_zoneX`` where X is a unique number.
At least 1 zone mapping is required.

.. code-block:: ini
   :name: certbot_azure_service_principal.ini
   :caption: Example config file using a service principal

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_client_secret = E-xqXU83Y-jzTI6xe9fs2YC~mck3ZzUih9
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

   dns_azure_environment = "AzurePublicCloud"

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

.. code-block:: ini
   :name: certbot_azure_service_principal_certificate.ini
   :caption: Example config file using a service principal with certificate

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_certificate_path = /path/to/certificate.pem
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

   dns_azure_environment = "AzurePublicCloud"

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

.. code-block:: ini
   :name: certbot_azure_user_msi.ini
   :caption: Example config file using user assigned MSI:

   dns_azure_msi_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

.. code-block:: ini
   :name: certbot_azure_system_msi.ini
   :caption: Example config file using system assigned MSI:

   dns_azure_msi_system_assigned = true

   dns_azure_environment = "AzurePublicCloud"

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

.. code-block:: ini
   :name: certbot_azure_cli.ini
   :caption: Example config file using Azure CLI credentials:

   dns_azure_use_cli_credentials = true

   dns_azure_environment = "AzurePublicCloud"

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

.. code-block:: ini
   :name: certbot_azure_workload_identity.ini
   :caption: Example config file using Azure Workload Identity credentials:

   dns_azure_use_workload_identity_credentials = true

   dns_azure_environment = "AzurePublicCloud"

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2


The path to this file can be provided interactively or using the
``--dns-azure-config`` command-line argument. Certbot records the path
to this file for use during renewal, but does not store the file's contents.

.. caution::
   You should protect these API credentials as you would the password to your
   Azure account. Users who can read this file can use these credentials
   to issue arbitrary API calls on your behalf. Users who can cause Certbot to
   run using these credentials can complete a ``dns-01`` challenge to acquire
   new certificates or revoke existing certificates for domains the identity
   has access to.

Certbot will emit a warning if it detects that the credentials file can be
accessed by other users on your system. The warning reads "Unsafe permissions
on configuration file", followed by the path to the config
file. This warning will be emitted each time Certbot uses the config file,
including for renewal, and cannot be silenced except by addressing the issue
(e.g., by using a command like ``chmod 600`` to restrict access to the file).


Azure Environment
-----------------

The Azure Cloud will default to ``AzurePublicCloud``, this is used to change
the authentication endpoint used when generating credentials. This option
can be specified in the config file using ``dns_azure_environment`` or 
via an environment variable ``AZURE_ENVIRONMENT``.

The supported values are:

========================================  =====================================
``AzurePublicCloud``                      https://management.azure.com/
``AzureUSGovernmentCloud``                https://management.usgovcloudapi.net/
``AzureChinaCloud``                       https://management.chinacloudapi.cn/
``AzureGermanCloud``                      https://management.microsoftazure.de/
========================================  =====================================

DNS delegation
--------------

DNS delegation, also known as DNS aliasing, is a process of allowing a secondary DNS zone to handle validation in place
of the primary zone. For example, you would like to acquire a certificate for ``example.com`` but have the validation
performed on a secondary domain ``example.org``. You would create a ``_acme-challenge.example.com`` CNAME on the
``example.com`` nameserver with the value of ``_acme-challenge.example.org``. The ACME server will resolve the CNAME and
validate the TXT record ``_acme-challenge.example.org`` instead. Certbot itself does not support CNAME aliasing,
therefore this plugin does what it can to support it.

The common reasons for DNS delegation are:
 * The primary DNS zone is hosted on a nameserver with no API access
 * Security concerns regarding access to the primary DNS zone

We'll use two domains for the examples below: ``foo.com`` and ``bar.com``.

Example: Primary Zone, no API Access
++++++++++++++++++++++++++++++++++++

Let's assume you wish to get a certificate for ``test.foo.com``, this will result in a validation record for
``_acme-challenge.test.foo.com``. Assuming you don't have API access to the ``foo.com`` zone, you can manually CNAME said
validation record to point it to ``bar.com``. E.g.
``_acme-challenge.test.foo.com CNAME -> _acme-challenge.test.foo.com.bar.com`` This will result in a TXT record called
``_acme-challenge.test.foo.com`` created in the ``bar.com`` zone.

This can be achieved by using the following config snippet

.. code-block:: ini
    :name: certbot_azure_alias1.ini
    :caption: Example configuration snippet for DNS delegation

    dns_azure_zone1 = test.foo.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a/resourceGroups/dns1/providers/Microsoft.Network/dnszones/bar.com

So when the Azure Certbot plugin gets requested to make ``_acme-challenge.test.foo.com``, the zone that record gets
created in is overridden to ``bar.com`` hence the entire ``_acme-challenge.test.foo.com`` is needed as the prefix in the
CNAME value before ``bar.com``.

Example: Delegation + more security
+++++++++++++++++++++++++++++++++++

One can go a step further than the step above when hosting records in Azure. Instead of granting Certbot write access
to an entire DNS Zone, you can grant access to specific records.

As with before, we shall get a certificate for ``test.foo.com``. We shall make a CNAME record like:
``_acme-challenge.test.foo.com CNAME test_validation.bar.com`` (yes it doesn't *need* ``_acme-challenge`` in this example).

Using a config like the following:

.. code-block:: ini
    :name: certbot_azure_alias2.ini
    :caption: Example configuration snippet for DNS delegation

    dns_azure_zone1 = test.foo.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a/resourceGroups/dns1/providers/Microsoft.Network/dnszones/bar.com/TXT/test_validation

This **requires** you to create a TXT record called ``test_validation`` in the ``bar.com`` zone, the value should be ``-`` and certbot should have IAM privileges to
write to that record explicitly. Now when the request is sent to the plugin to create ``_acme-challenge.test.foo.com``
the zone its created in will be overridden with ``bar.com`` and the validation record will be overridden with ``test_validation``. This
effectively does the same thing as if certbot had actually resolved the CNAME (which it doesn't).

Now one caveat here, if you assign specific IAM roles to an individual record, they'll be lost when the record is cleaned up and deleted.
Which means when it comes to renewal, it'll fail as it has no IAM privileges to update said record as it no longer exists. For this reason
when the config has record ID's in it, it will not delete the validation records, it will just set its value to ``-``
(hence you were told to set this initially).

This example can be simplified to allow you to reduce the certbot permissions but **not** do CNAME delegation, so
for ``test.foo.com`` you would make a TXT record for ``_acme-challenge.test.foo.com`` with the value of ``-`` and then use a config
snippet like:

.. code-block:: ini
    :name: certbot_azure_moresecure.ini
    :caption: Example configuration snippet for individual record permissions

    dns_azure_zone1 = test.foo.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a/resourceGroups/dns1/providers/Microsoft.Network/dnszones/foo.com/TXT/_acme-validation.test

This will override the zone to foo.com (which ``test`` is already in) and the validation record (though it's overridden to the same thing) but now
it will not delete said validation record.


Generic Certbot Examples
------------------------

.. code-block:: bash
   :caption: To acquire a certificate for ``example.com``

   certbot certonly \\
     --dns-azure-config ~/.secrets/certbot/azure.ini \\
     -d example.com

.. code-block:: bash
   :caption: To acquire a single certificate for both ``example.com`` and
             ``example.org``

   certbot certonly \\
     --dns-azure-config ~/.secrets/certbot/azure.ini \\
     -d example.com \\
     -d example.org

To run in a non-interactive manner:

.. code-block:: bash
   :caption: Non-interactive
   
   certbot certonly \\
     --authenticator dns-azure \\
     --preferred-challenges dns \\
     --noninteractive \\
     --agree-tos \\
     --dns-azure-config ~/.secrets/certbot/azure.ini \\
     -d example.com

"""
