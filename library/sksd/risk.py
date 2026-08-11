"""
risk.py -- classificacao de risco das operacoes de diff produzidas por ir_diff.

Cada EditOp recebe um peso 0-100 por casamento de prefixo mais longo contra
uma tabela de risco indexada pelo caminho normalizado do esquema (tpath).
O peso determina PRIORIDADE e NUMERO de revisores exigidos no Merge Request
de drift -- nunca se um humano revisa ou nao (isso e sempre obrigatorio).

Os pesos abaixo sao julgamento de engenharia; calibrar contra o historico
real de incidentes do seu parque antes de usar em producao.
"""
from typing import Dict, Tuple

from .ir_diff import EditOp, Path

RISK_WEIGHTS: Dict[Path, int] = {
    ("network-instance", "*", "protocols", "bgp", "neighbor", "*", "peer-as"): 95,
    ("network-instance", "*", "protocols", "bgp", "neighbor"): 90,
    ("network-instance", "*", "protocols", "bgp", "neighbor", "*", "admin-state"): 85,
    ("acl", "ipv4-filter", "entry"): 85,
    ("interface", "*", "admin-state"): 70,
    ("interface", "*", "subinterface", "*", "ipv4", "address"): 60,
    ("network-instance", "*", "protocols", "ospf", "instance", "*", "area"): 55,
    ("interface", "*", "description"): 10,
    ("system",): 15,
}
DEFAULT_RISK = 50


def _weight_for(tpath: Path) -> int:
    """Casamento de prefixo mais longo contra RISK_WEIGHTS."""
    best = DEFAULT_RISK
    best_len = -1
    for prefix, weight in RISK_WEIGHTS.items():
        if tpath[: len(prefix)] == prefix and len(prefix) > best_len:
            best, best_len = weight, len(prefix)
    return best


def classify_risk(op: EditOp) -> Tuple[int, str]:
    weight = _weight_for(op.tpath)
    if weight >= 80:
        return weight, "HIGH"
    if weight >= 40:
        return weight, "MEDIUM"
    return weight, "LOW"
