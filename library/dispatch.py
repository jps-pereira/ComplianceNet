"""
dispatch.py -- motor de decisao de protocolo (NETCONF vs. CLI).

Consulta o NetBox e retorna, para um device, qual protocolo o pipeline deve
usar para deploy/dry-run: 'netconf' (caminho principal) ou 'cli' (fallback
via NAPALM/Netmiko + templates Jinja2), com base no custom field
'netconf_enabled' cadastrado no NetBox para aquele device.

O operador nunca precisa saber qual caminho foi usado -- este modulo decide
isso de forma transparente em playbooks/dry_run.yml e playbooks/deploy.yml.
"""
import sys
import requests


def get_transport(device_name: str, netbox_url: str, netbox_token: str) -> str:
    """Consulta o NetBox e retorna 'netconf' ou 'cli' para o device informado."""
    r = requests.get(
        f"{netbox_url}/api/dcim/devices/?name={device_name}",
        headers={"Authorization": f"Token {netbox_token}"},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return "cli"
    enabled = results[0].get("custom_fields", {}).get("netconf_enabled", False)
    return "netconf" if enabled else "cli"


if __name__ == "__main__":
    # Uso: python3 dispatch.py <device_name> <netbox_url> <netbox_token>
    print(get_transport(sys.argv[1], sys.argv[2], sys.argv[3]))
