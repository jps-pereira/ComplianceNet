"""
drift_detector.py -- compara estado observado vs. desejado e abre MR de drift.

Fluxo: coleta (drift_collector.get_running_config) -> parse
(config_parser.parse_running_config) -> diff contra host_vars/<device>.yaml
-> se houver divergencia, cria branch, commita o YAML observado e abre um
Merge Request via API do GitLab com a tabela de diff no corpo.

Nota: esta versao usa comparacao de dicionario simples e e suscetivel a
falso-positivo quando um device reordena listas entre coletas sem mudanca
real. Para um motor de diff que resolve isso por alinhamento de chave YANG,
ver library/sksd/ir_diff.py e docs/architecture.md.
"""
import datetime
import os
import subprocess
from pathlib import Path

import requests
import yaml

from .config_parser import parse_running_config

GITLAB_URL = os.environ["CI_SERVER_URL"]
PROJECT_ID = os.environ["CI_PROJECT_ID"]
GITLAB_TOKEN = os.environ["DRIFT_BOT_TOKEN"]


def detect_and_report(device_name: str, raw: str, platform: str, repo: Path) -> None:
    desired = yaml.safe_load((repo / "host_vars" / f"{device_name}.yaml").read_text())
    actual = parse_running_config(device_name, raw, platform)

    diff = {
        k: {"desired": desired.get(k), "actual": actual.get(k)}
        for k in set(desired) | set(actual)
        if desired.get(k) != actual.get(k)
    }
    if not diff:
        return  # sem drift -- nenhuma acao necessaria

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M")
    branch = f"drift/{device_name}-{ts}"
    target = repo / "host_vars" / f"{device_name}.yaml"

    subprocess.run(["git", "checkout", "-b", branch], cwd=repo, check=True)
    target.write_text(yaml.dump(actual, default_flow_style=False, allow_unicode=True))
    subprocess.run(["git", "add", str(target)], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore(drift): sync {device_name} -- mudanca fora do pipeline"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", branch], cwd=repo, check=True)

    rows = "".join(f'| `{k}` | `{v["desired"]}` | `{v["actual"]}` |\n' for k, v in diff.items())
    desc = (
        f"## Drift detectado: `{device_name}`\n\n"
        f"Mudanca aplicada diretamente no equipamento, fora do pipeline.\n\n"
        f"| Campo | Desejado (Git) | Atual (equipamento) |\n"
        f"|---|---|---|\n{rows}\n"
        f"**Aceitar:** fazer merge deste MR -- Git passa a refletir o equipamento.\n"
        f"**Reverter:** fechar sem merge e executar o deploy normal."
    )
    r = requests.post(
        f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/merge_requests",
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
        json={
            "source_branch": branch,
            "target_branch": "main",
            "title": f"[DRIFT] {device_name} -- config fora do pipeline",
            "description": desc,
            "labels": "drift,compliance,needs-review",
            "remove_source_branch": True,
        },
        timeout=15,
    )
    r.raise_for_status()
