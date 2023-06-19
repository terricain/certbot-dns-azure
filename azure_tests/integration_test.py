import os
import subprocess
import uuid
from typing import TYPE_CHECKING, List, Tuple

import pytest
from azure.mgmt.dns import DnsManagementClient
from azure.identity import ClientSecretCredential, AzureCliCredential

if TYPE_CHECKING:
    import pathlib

AZURE_ENV = os.getenv("AZURE_ENVIRONMENT", "AzurePublicCloud")
EMAIL = os.getenv('EMAIL', 'NOT_AN_EMAIL')

azure_creds = pytest.mark.skipif(
    any(env not in os.environ for env in ['AZURE_TENANT_ID', 'EMAIL']),
    reason="Missing 'AZURE_TENANT_ID' or 'EMAIL' environment variables"
)

SUBSCRIPTION_ID = '90907259-f568-40c9-be09-768317e458ae'
RESOURCE_GROUP = 'certbot'

ZONES = {
    'zone1.certbot-dns-azure.co.uk': '/subscriptions/90907259-f568-40c9-be09-768317e458ae/resourceGroups/certbot',  # /providers/Microsoft.Network/dnszones/zone1.certbot-dns-azure.co.uk
    'zone2.certbot-dns-azure.co.uk': '/subscriptions/90907259-f568-40c9-be09-768317e458ae/resourceGroups/certbot',  # providers/Microsoft.Network/dnszones/zone2.certbot-dns-azure.co.uk
    'del2.certbot-dns-azure.co.uk': '/subscriptions/90907259-f568-40c9-be09-768317e458ae/resourceGroups/certbot',
}
DELEGATION_ZONE = '/subscriptions/90907259-f568-40c9-be09-768317e458ae/resourceGroups/certbot/providers/Microsoft.Network/dnsZones/del2.certbot-dns-azure.co.uk'
DELEGATION_ZONE2 = '/subscriptions/90907259-f568-40c9-be09-768317e458ae/resourceGroups/certbot/providers/Microsoft.Network/dnsZones/del1.certbot-dns-azure.co.uk/TXT/other'


def get_cert_names(count: int = 1) -> List[str]:
    return [uuid.uuid4().hex for _ in range(count)]


@pytest.fixture(scope='session')
def azure_dns_client() -> DnsManagementClient:
    if 'AZURE_CLIENT_SECRET' in os.environ:
        creds = ClientSecretCredential(
            client_id=os.environ['AZURE_CLIENT_ID'],
            client_secret=os.environ['AZURE_CLIENT_SECRET'],
            tenant_id=os.environ['AZURE_TENANT_ID'],
            authority='https://login.microsoftonline.com/'
        )
    else:
        creds = AzureCliCredential(tenant_id=os.environ['AZURE_TENANT_ID'])
    return DnsManagementClient(creds, SUBSCRIPTION_ID, None, 'https://management.azure.com/', credential_scopes=['https://management.azure.com//.default'])


@pytest.fixture(scope='function', autouse=True)
def cleanup_dns(azure_dns_client):
    """
    Cleans up all records in all zones defined in ZONES

    :param azure_dns_client: pytest dns client fixture
    """
    yield

    for zone in ZONES:
        to_delete = []
        for rr in azure_dns_client.record_sets.list_by_dns_zone(RESOURCE_GROUP, zone):
            rr_type = rr.type.rsplit('/', 1)[-1]
            if rr_type in ('NS', 'SOA'):
                continue

            to_delete.append((rr.name, rr_type))
        for rr_name, rr_type in to_delete:
            try:
                azure_dns_client.record_sets.delete(RESOURCE_GROUP, zone, rr_name, rr_type)
                print(f"Deleted {zone}/{rr_name}")
            except Exception as err:
                print(f"Tried to delete {zone}/{rr_name}, got: {err}")


def create_config(tmpdir: 'pathlib.Path', zones: List[str]) -> str:
    """
    Creates a config file for certbot azure dns

    :param tmpdir: Temporary pytest fixture
    :param zones: List of zone entries for config
    :returns: Filepath to config
    """
    config = {
        # 'dns_azure_sp_client_id': os.environ['AZURE_CLIENT_ID'],
        # 'dns_azure_sp_client_secret': os.environ['AZURE_CLIENT_SECRET'],
        'dns_azure_use_cli_credentials': 'true',
        'dns_azure_tenant_id': os.environ['AZURE_TENANT_ID'],
        'dns_azure_environment': AZURE_ENV,
    }
    for index, zone in enumerate(zones, start=1):
        config[f"dns_azure_zone{index}"] = zone

    config_text = '\n'.join([' = '.join(item) for item in config.items()]) + '\n'
    config_file = tmpdir / "config.ini"
    config_file.write_text(config_text)
    config_file.chmod(0o600)
    return str(config_file)


def run_certbot(certbot_path: 'pathlib.Path', config_file: str, fqdns: List[str], *, dry_run: bool = False) -> Tuple[subprocess.Popen, str, str]:
    args = [
        'certbot', 'certonly', '--authenticator', 'dns-azure', '--preferred-challenges', 'dns', '--noninteractive',
        '--agree-tos',
        '--email', EMAIL,
        '--config-dir', certbot_path, '--work-dir', certbot_path, '--logs-dir', certbot_path,
        '--dns-azure-config', config_file,
    ]
    if dry_run:
        args.append('--dry-run')
    for fqdn in fqdns:
        args.extend(['-d', fqdn])

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        print(f"Error, return code {proc.returncode}\nSTDERR:\n{stderr}\nSTDOUT:\n{stdout}")
        pytest.fail()

    return proc, stdout, stderr


@azure_creds
def test_single_zone(tmp_path, azure_dns_client):
    """
    Tests getting a certificate for a single zone
    """
    certbot_path = tmp_path / "certbot"
    zone = 'zone1.certbot-dns-azure.co.uk'
    rr_name = get_cert_names(1)[0]
    fqdn = f"{rr_name}.{zone}"

    zone_entry = f"{zone}:{ZONES[zone]}"
    config_file = create_config(tmp_path, [zone_entry])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn])

    cert_path = certbot_path / 'archive' / fqdn / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")


@azure_creds
def test_multi_zone(tmp_path, azure_dns_client):
    """
    Tests getting a certificate for multiple zones
    """
    certbot_path = tmp_path / "certbot"
    zone1 = 'zone1.certbot-dns-azure.co.uk'
    zone2 = 'zone2.certbot-dns-azure.co.uk'

    rr_name1, rr_name2 = get_cert_names(2)
    fqdn1 = f"{rr_name1}.{zone1}"
    fqdn2 = f"{rr_name2}.{zone2}"

    zone_entry1 = f"{zone1}:{ZONES[zone1]}"
    zone_entry2 = f"{zone2}:{ZONES[zone2]}"
    config_file = create_config(tmp_path, [zone_entry1, zone_entry2])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn1, fqdn2])

    cert_path1 = certbot_path / 'archive' / fqdn1 / 'cert1.pem'
    cert_path2 = certbot_path / 'archive' / fqdn2 / 'cert1.pem'
    if not cert_path1.exists() and not cert_path2.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path1} or {cert_path2} does not exist")


@azure_creds
def test_delegation_other_domain(tmp_path, azure_dns_client):
    """
    Tests getting a certificate for a single zone
    """
    certbot_path = tmp_path / "certbot"
    fqdn = 'del1.certbot-dns-azure.co.uk'

    # domain is del1, but we're explicitly overriding the zone to del2
    config_file = create_config(tmp_path, [
        f"{fqdn}:{DELEGATION_ZONE}"
    ])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn])

    cert_path = certbot_path / 'archive' / fqdn / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")


@azure_creds
def test_delegation_specific_record(tmp_path, azure_dns_client):
    """
    Tests getting a certificate for a single zone
    """
    certbot_path = tmp_path / "certbot"
    fqdn = 'test.del1.certbot-dns-azure.co.uk'

    # domain is del1, but we're explicitly overriding to an alternate record of del1
    config_file = create_config(tmp_path, [
        f"{fqdn}:{DELEGATION_ZONE2}"
    ])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn])

    cert_path = certbot_path / 'archive' / fqdn / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")