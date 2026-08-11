"""
drift_collector.py -- coleta de running-config para deteccao de drift.

Conecta via NETCONF direto (ncclient), no mesmo padrao ja usado em
backup.py, dry_run.py e deploy.py. Nao depende de API HTTP de terceiros.
"""
import os

from ncclient import manager

NETCONF_USERNAME = os.environ["NETCONF_USERNAME"]
NETCONF_PASSWORD = os.environ["NETCONF_PASSWORD"]


def get_running_config(mgmt_ip: str) -> str:
    """Retorna a running-config bruta (XML) de um device via NETCONF."""
    m = manager.connect(
        host=mgmt_ip,
        port=830,
        username=NETCONF_USERNAME,
        password=NETCONF_PASSWORD,
        hostkey_verify=False,
        device_params={"name": "default"},
        allow_agent=False,
        look_for_keys=False,
        timeout=15,
    )
    c = m.get_config(source="running")
    m.close_session()
    return c.data_xml
