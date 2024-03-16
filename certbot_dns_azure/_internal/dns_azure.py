"""DNS Authenticator for Azure DNS."""
import logging
import time
import random
from os import getenv
from typing import Dict, Tuple

from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet, TxtRecord
from azure.core.exceptions import HttpResponseError
from azure.core.utils import CaseInsensitiveDict
from azure.identity import ClientSecretCredential, ManagedIdentityCredential, CertificateCredential, AzureCliCredential, WorkloadIdentityCredential

from certbot import errors
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)
logging.getLogger('azure').setLevel(logging.WARNING)


class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for Azure DNS

    This Authenticator uses the Azure DNS API to fulfill a dns-01 challenge.
    """

    description = ('Obtain certificates using a DNS TXT record (if you are using '
                   'Azure for DNS).')
    ttl = 120

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credential = None
        self.domain_zoneid = {}  # type: Dict[str, str]

        # Azure Environmental Support
        self._azure_environment = getenv("AZURE_ENVIRONMENT", "AzurePublicCloud").lower()
        self._azure_endpoints = {
            "azurepubliccloud": {
                "ResourceManagerEndpoint": "https://management.azure.com/",
                "ActiveDirectoryEndpoint": "https://login.microsoftonline.com/"
            },
            "azureusgovernmentcloud": {
                "ResourceManagerEndpoint": "https://management.usgovcloudapi.net/",
                "ActiveDirectoryEndpoint": "https://login.microsoftonline.us/"
            },
            "azurechinacloud": {
                "ResourceManagerEndpoint": "https://management.chinacloudapi.cn/",
                "ActiveDirectoryEndpoint": "https://login.chinacloudapi.cn/"
            },
            "azuregermancloud": {
                "ResourceManagerEndpoint": "https://management.microsoftazure.de/",
                "ActiveDirectoryEndpoint": "https://login.microsoftonline.de/"
            }
        }

    @classmethod
    def add_parser_arguments(cls, add):  # pylint: disable=arguments-differ
        super(Authenticator, cls).add_parser_arguments(add)
        add('config', help='Azure config INI file.')
        add('credentials', help='Azure config INI file. Fallback for legacy integrations')

    def more_info(self):  # pylint: disable=missing-function-docstring
        return 'This plugin configures a DNS TXT record to respond to a dns-01 challenge using ' + \
               'the Azure DNS API.'

    def _validate_credentials(self, credentials):
        sp_client_id = credentials.conf('sp_client_id')
        sp_client_secret = credentials.conf('sp_client_secret')
        sp_certificate_path = credentials.conf('sp_certificate_path')
        tenant_id = credentials.conf('tenant_id')
        has_sp = all((sp_client_id, any((sp_client_secret, sp_certificate_path)), tenant_id))

        msi_client_id = credentials.conf('msi_client_id')
        msi_system_assigned = credentials.conf('msi_system_assigned')

        use_azure_cli_creds = credentials.conf('use_cli_credentials')

        use_workload_identity_creds = credentials.conf('use_workload_identity_credentials')

        if not any((has_sp, msi_system_assigned, msi_client_id, use_azure_cli_creds, use_workload_identity_creds)):
            raise errors.PluginError('{}: No authentication methods have been '
                                     'configured for Azure DNS. Either configure '
                                     'a service principal, system/user assigned '
                                     'managed identity or configure the use of '
                                     'azure cli or workload identity credentials'.format(credentials.confobj.filename))

        has_zone_mapping = any((key for key in credentials.confobj.keys() if 'azure_zone' in key))

        if not has_zone_mapping:
            raise errors.PluginError('{}: At least one zone mapping needs to be provided,'
                                     ' e.g dns_azure_zone1 = DOMAIN:DNS_ZONE_RESOURCE_GROUP_ID'
                                     ''.format(credentials.confobj.filename))

        # Azure Environment
        environment = credentials.conf('environment')

        if environment:
            self._azure_environment = environment.lower()

        self._arm_endpoint = self._azure_endpoints[self._azure_environment]["ResourceManagerEndpoint"]
        self._aad_endpoint = self._azure_endpoints[self._azure_environment]["ActiveDirectoryEndpoint"]
        
        # Check we have key value
        dns_zone_mapping_items_has_colon = [':' in value
                                            for key, value in credentials.confobj.items()
                                            if 'azure_zone' in key]
        if not all(dns_zone_mapping_items_has_colon):
            raise errors.PluginError('{}: DNS Zone mapping is not in the format of '
                                     'DOMAIN:DNS_ZONE_RESOURCE_GROUP_ID'
                                     ''.format(credentials.confobj.filename))

    def _setup_credentials(self):
        # Alias's dns-azure-credentials -> dns-azure-config
        if self.config.namespace.dns_azure_credentials:
            self.config.namespace.dns_azure_config = self.config.namespace.dns_azure_credentials

        valid_creds = self._configure_credentials(
            'config',
            'Azure config INI file',
            None,
            self._validate_credentials
        )

        # Convert dns_azure_zoneX = key:value into key:value
        dns_zone_mapping_items = [value for key, value in valid_creds.confobj.items()
                                  if 'azure_zone' in key]
        self.domain_zoneid = dict([item.split(':', 1) for item in dns_zone_mapping_items])

        # Figure out which credential type we're going to use
        sp_client_id = valid_creds.conf('sp_client_id')
        sp_client_secret = valid_creds.conf('sp_client_secret')
        sp_certificate_path = valid_creds.conf('sp_certificate_path')
        tenant_id = valid_creds.conf('tenant_id')
        msi_client_id = valid_creds.conf('msi_client_id')
        use_azure_cli_creds = valid_creds.conf('use_cli_credentials')
        use_workload_identity_creds = valid_creds.conf('use_workload_identity_credentials')

        self.credential = self._get_azure_credentials(
            sp_client_id, sp_client_secret, sp_certificate_path, tenant_id, msi_client_id, use_azure_cli_creds, use_workload_identity_creds, self._aad_endpoint
        )

    @staticmethod
    def _get_azure_credentials(client_id=None, client_secret=None, certificate_path=None, tenant_id=None, msi_client_id=None,
                               use_azure_cli_creds=None, use_workload_identity_creds=None, aad_endpoint=None):
        has_sp = all((client_id, client_secret, tenant_id))
        has_sp_cert = all((client_id, certificate_path, tenant_id))
        if use_azure_cli_creds:  # TODO move to DefaultAzureCredential
            return AzureCliCredential(tenant_id=tenant_id)
        elif use_workload_identity_creds:
            return WorkloadIdentityCredential(tenant_id=tenant_id)
        elif has_sp:
            return ClientSecretCredential(
                client_id=client_id,
                client_secret=client_secret,
                tenant_id=tenant_id,
                authority=aad_endpoint
            )
        elif has_sp_cert:
            return CertificateCredential(
                client_id=client_id,
                certificate_path=certificate_path,
                tenant_id=tenant_id,
                authority=aad_endpoint
            )
        elif msi_client_id:
            return ManagedIdentityCredential(client_id=msi_client_id)
        else:
            return ManagedIdentityCredential()

    def _get_ids_for_domain(self, domain: str, validation_name: str) -> Tuple[str, str, str, str, bool]:
        """
        :param domain: Domain/subdomain to look up the closest parent in the config file
        :param validation_name: DNS challenge record name, fully qualified

        This returns:
        * The Azure DNS zone for which to add records to
        * The subscription ID for said zone
        * The resource group for said zone
        * The relative validation record name (or if explicitly overrided with an ID, an alternate record name)
        * If the validation record can be deleted, if its explicitly overrided, it wont be deleted but set to `-`
        """
        # So if the config contains domain.io and test.domain.io
        # and we want to renew, we'd prefer test.domain.io.
        # Sort domains by longest first and then attempt to find the right one.
        # This should work better, as then a.b.test.domain.io would pick domain.io irrelevant
        # of its order in the config
        azure_domains = sorted(self.domain_zoneid.keys(), key=lambda domain: len(domain), reverse=True)

        try:
            for azure_dns_domain in azure_domains:
                # Look to see if domain ends with key, to cover subdomains
                if domain.endswith(azure_dns_domain):
                    zone_id = self.domain_zoneid[azure_dns_domain]

                    try:
                        resource = self.parse_azure_resource_id(zone_id)
                    except ValueError as exc:
                        raise errors.PluginError('Failed to parse resource ID for {}: {}'
                                                 .format(domain, zone_id)) from exc
                    subscription_id = resource.get('subscriptions')
                    rg_name = resource.get('resourceGroups')
                    if 'dnsZones' in resource:  # If we're manually specifying an alternate zone to use, override.
                        azure_dns_domain = resource.get('dnsZones')
                    relative_validation_name = self._get_relative_domain(validation_name, azure_dns_domain)
                    can_delete = True
                    if 'TXT' in resource:  # If we're explicitly specifing a destination record, use instead.
                        relative_validation_name = resource.get('TXT')
                        can_delete = False  # If we're specifying a specific record, dont delete it

                    return azure_dns_domain, subscription_id, rg_name, relative_validation_name, can_delete
            else:
                raise errors.PluginError('Domain {} does not have a valid domain to '
                                         'resource group id mapping'.format(domain))
        except IndexError:
            raise errors.PluginError('Domain {} has an invalid resource group id'.format(domain))

    @staticmethod
    def _get_relative_domain(fqdn: str, domain: str) -> str:
        if fqdn == domain:
            return '@'
        return fqdn.replace(domain, '').strip('.')

    def _perform(self, domain, validation_name, validation, retry_attempt=0):
        azure_domain, subscription_id, resource_group_name, validation_name, _ = self._get_ids_for_domain(domain, validation_name)
        client = self._get_azure_client(subscription_id)

        # Check to see if there are any existing TXT validation record values
        txt_value = {validation}
        etag = None
        try:
            existing_rr = client.record_sets.get(
                resource_group_name=resource_group_name,
                zone_name=azure_domain,
                relative_record_set_name=validation_name,
                record_type='TXT')
            etag = existing_rr.etag
            for record in existing_rr.txt_records:
                for value in record.value:
                    if value == '-':
                        continue
                    txt_value.add(value)
        except HttpResponseError as err:
            if err.status_code != 404:  # Ignore RR not found
                raise errors.PluginError('Failed to check TXT record for domain '
                                         '{}, error: {}'.format(domain, err))

        try:
            client.record_sets.create_or_update(
                resource_group_name=resource_group_name,
                zone_name=azure_domain,
                relative_record_set_name=validation_name,
                record_type='TXT',
                if_match=etag,
                parameters=RecordSet(ttl=self.ttl, txt_records=[TxtRecord(value=[v]) for v in txt_value])
            )
        except HttpResponseError as err:
            if err.status_code == 412:
                # There is some parallel access on this record, sleep a random amount and try again.
                if retry_attempt > 10:
                    raise errors.PluginError('Failed to add TXT record for domain {}, max retries due to concurrent access exceeded'
                                             ', error: {}'.format(domain, err))
                sleep_secs = random.randint(1, 10)
                retry_attempt += 1
                logger.warning("Concurrent access to record {}, sleeping {} seconds, retry attempt: {}".format(domain, sleep_secs, retry_attempt))
                time.sleep(sleep_secs)
                self._perform(domain, validation_name, validation, retry_attempt)
            else:
                raise errors.PluginError('Failed to add TXT record to domain '
                                         '{}, error: {}'.format(domain, err))

    def _cleanup(self, domain, validation_name, validation, retry_attempt=0):
        if self.credential is None:
            self._setup_credentials()

        azure_domain, subscription_id, resource_group_name, validation_name, can_delete = self._get_ids_for_domain(domain, validation_name)
        client = self._get_azure_client(subscription_id)

        txt_value = set()
        etag = None
        try:
            existing_rr = client.record_sets.get(resource_group_name=resource_group_name,
                                                 zone_name=azure_domain,
                                                 relative_record_set_name=validation_name,
                                                 record_type='TXT')
            etag = existing_rr.etag
            for record in existing_rr.txt_records:
                for value in record.value:
                    txt_value.add(value)
        except HttpResponseError as err:
            if err.status_code != 404:  # Ignore RR not found
                raise errors.PluginError('Failed to check TXT record for domain '
                                         '{}, error: {}'.format(domain, err))

        txt_value -= {validation}

        try:
            if txt_value:
                client.record_sets.create_or_update(
                    resource_group_name=resource_group_name,
                    zone_name=azure_domain,
                    relative_record_set_name=validation_name,
                    record_type='TXT',
                    if_match=etag,
                    parameters=RecordSet(ttl=self.ttl,
                                         txt_records=[TxtRecord(value=[v]) for v in txt_value])
                )
            else:
                if can_delete:
                    client.record_sets.delete(
                        resource_group_name=resource_group_name,
                        zone_name=azure_domain,
                        relative_record_set_name=validation_name,
                        if_match=etag,
                        record_type='TXT'
                    )
                else:
                    client.record_sets.create_or_update(  # We've manually specified a record, so dont delete, set to -
                        resource_group_name=resource_group_name,
                        zone_name=azure_domain,
                        relative_record_set_name=validation_name,
                        if_match=etag,
                        record_type='TXT',
                        parameters=RecordSet(ttl=self.ttl, txt_records=[TxtRecord(value=['-'])])
                    )
        except HttpResponseError as err:
            if err.status_code == 412:
                # There is some parallel access on this record, sleep a random amount and try again.
                if retry_attempt > 10:
                    raise errors.PluginError('Failed to remove/empty TXT record for domain {}, max retries due to concurrent access exceeded'
                                             ', error: {}'.format(domain, err))
                sleep_secs = random.randint(1, 10)
                retry_attempt += 1
                logger.warning("Concurrent access to record {}, sleeping {} seconds, retry attempt: {}".format(domain, sleep_secs, retry_attempt))
                time.sleep(sleep_secs)
                self._cleanup(domain, validation_name, validation, retry_attempt)
            elif err.status_code != 404:  # Ignore RR not found
                raise errors.PluginError('Failed to remove/empty TXT record for domain '
                                         '{}, error: {}'.format(domain, err))

    def _get_azure_client(self, subscription_id):
        """
        Gets azure DNS client

        :param subscription_id: Azure subscription ID
        :type subscription_id: str
        :return: Azure DNS client
        :rtype: DnsManagementClient
        """
        return DnsManagementClient(self.credential, subscription_id, None, self._arm_endpoint, credential_scopes=[self._arm_endpoint + "/.default"])

    @staticmethod
    def parse_azure_resource_id(resource_id):
        rsrc_id = resource_id
        if rsrc_id.startswith('/'):
            rsrc_id = rsrc_id[1:]

        if rsrc_id.endswith('/'):
            rsrc_id = rsrc_id[:-1]

        if '/' not in rsrc_id:
            raise ValueError('Invalid resource ID: {}'.format(resource_id))

        parts = rsrc_id.split('/')
        if (len(parts) % 2) != 0 or '' in parts:
            raise ValueError('Invalid resource ID: {}'.format(resource_id))
        return CaseInsensitiveDict(zip(parts[0::2], parts[1::2]))
