"""
backup.py -- backup de configuracao via NETCONF direto (sem depender de Oxidized).

Historico de decisao: Oxidized foi avaliado primeiro, mas nao possui modelo
nativo para todos os NOS do parque-alvo (ex.: Nokia SR Linux expoe apenas
'sros', o SR OS classico, com CLI incompativel com a sr_cli do SR Linux). A
investigacao de um modelo customizado nao encontrou causa raiz para o erro
'NoNodesFound' apos varias hipoteses testadas. Decisao adotada: via de mao
unica reaproveitando o mesmo cliente NETCONF (ncclient) ja usado no resto do
pipeline (dry_run.py, deploy.py) -- reduz superficie de dependencias.

Um repositorio Git DEDICADO (separado do repositorio de configuracoes)
guarda o estado observado; commit automatico apenas quando ha mudanca real
(idempotente). Este script NAO escreve de volta em host_vars/: estado
observado e estado desejado sao conceitos distintos por design (ver
docs/architecture.md).
"""
import os
import subprocess
from pathlib import Path

import yaml
from ncclient import manager

BACKUP_REPO = Path(os.environ.get("BACKUP_REPO", "/srv/config-backups"))
REPO_PATH = Path(os.environ.get("REPO_PATH", "."))
NETCONF_USERNAME = os.environ["NETCONF_USERNAME"]
NETCONF_PASSWORD = os.environ["NETCONF_PASSWORD"]


def fetch_running_config(mgmt_ip: str) -> str:
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


def backup_all() -> None:
    hv_path = REPO_PATH / "host_vars"
    BACKUP_REPO.mkdir(parents=True, exist_ok=True)
    changed = []

    for hv_file in sorted(hv_path.glob("*.yaml")):
        if hv_file.name == ".gitkeep":
            continue
        hostvars = yaml.safe_load(hv_file.read_text())
        hostname = hostvars["hostname"]
        mgmt_ip = hostvars["mgmt_ip"]

        raw = fetch_running_config(mgmt_ip)
        target = BACKUP_REPO / f"{hostname}.xml"
        if not target.exists() or target.read_text() != raw:
            target.write_text(raw)
            changed.append(hostname)
            print(f"Backup atualizado: {hostname}")

    if changed:
        subprocess.run(["git", "add", "."], cwd=BACKUP_REPO, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"backup: {len(changed)} device(s) atualizado(s)"],
            cwd=BACKUP_REPO,
            check=True,
        )
        subprocess.run(["git", "push"], cwd=BACKUP_REPO, check=True)
    else:
        print("Nenhuma mudanca detectada em nenhum device.")


if __name__ == "__main__":
    backup_all()
