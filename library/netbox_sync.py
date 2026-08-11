"""
netbox_sync.py -- sincroniza devices do NetBox para host_vars/ no repositorio Git.

O NetBox e a UNICA fonte da verdade para o inventario. Este script gera um
arquivo YAML por device ativo em host_vars/, refletindo os custom fields
cadastrados no NetBox. O job de CI correspondente (ver pipeline/.gitlab-ci.yml)
commita as mudancas em uma branch nova e abre um Merge Request automatico --
o operador aprova antes de qualquer alteracao entrar na branch principal.

Nunca criar host_vars/ manualmente: qualquer arquivo fora deste fluxo e
sobrescrito na proxima execucao.
"""
import os
import sys
from pathlib import Path

import requests
import yaml

NETBOX_URL = os.environ["NETBOX_URL"]
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]
REPO_PATH = Path(os.environ.get("REPO_PATH", "."))
HDR = {"Authorization": f"Token {NETBOX_TOKEN}"}


def get_devices() -> list:
    r = requests.get(
        f"{NETBOX_URL}/api/dcim/devices/?status=active&limit=200",
        headers=HDR,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["results"]


def device_to_hostvars(device: dict) -> dict:
    cf = device.get("custom_fields", {})
    primary_ip = device.get("primary_ip4") or {}
    ip_str = primary_ip.get("address", "").split("/")[0]
    loopback = cf.get("loopback_ip", "")
    return {
        "hostname": device["name"],
        "mgmt_ip": ip_str,
        "loopback_ip": loopback,
        "ospf_router_id": loopback,
        "platform": (device.get("platform") or {}).get("slug", "generic"),
        "netconf_enabled": cf.get("netconf_enabled", False),
        "netconf_payload": cf.get("netconf_payload", "bgp_peer"),
        "bgp_peers": cf.get("bgp_peers", []),
        "acl_mgmt_permit": cf.get("acl_mgmt_permit", []),
    }


def sync() -> list:
    devices = get_devices()
    hv_path = REPO_PATH / "host_vars"
    hv_path.mkdir(exist_ok=True)
    changed = []
    current_names = set()

    for device in devices:
        name = device["name"]
        hostvars = device_to_hostvars(device)
        target = hv_path / f"{name}.yaml"
        new_yaml = yaml.dump(hostvars, default_flow_style=False, allow_unicode=True)
        if not target.exists() or target.read_text() != new_yaml:
            target.write_text(new_yaml)
            changed.append(name)
            print(f"Atualizado: {name}")
        current_names.add(name)

    # Remover arquivos de devices que saíram do NetBox (status != active)
    for f in hv_path.glob("*.yaml"):
        if f.stem not in current_names and f.name != ".gitkeep":
            f.unlink()
            changed.append(f"REMOVIDO: {f.stem}")
            print(f"Removido: {f.stem} (nao encontrado no NetBox)")

    return changed


if __name__ == "__main__":
    changes = sync()
    if changes:
        print(f"\n{len(changes)} arquivo(s) alterado(s): {changes}")
        sys.exit(0)  # saida 0 = houve mudancas (CI abre MR)
    print("Nenhuma mudanca detectada.")
    sys.exit(2)  # saida 2 = sem mudancas (CI nao abre MR)
