"""
SKSD -- Schema-Keyed Semantic Diff

Ideia central: um algoritmo generico de tree-edit-distance trata a
configuracao como uma floresta sem rotulo e BUSCA o alinhamento mais
barato entre nos -- O(n^3) no pior caso, sem saber que uma 'list' YANG
com chave declarada deveria ser alinhada pela chave, nao por posicao.

SKSD explora a estrutura ja presente no esquema YANG:
  - 'list' com chave declarada -> alinhar por chave (hash join, O(n))
  - 'leaf-list' sem ordenacao   -> comparar como conjunto
  - listas onde ordem importa   -> diff de sequencia (LCS-adjacente)
  - containers/leaves           -> recursao estrutural / igualdade

Ver docs/architecture.md para a motivacao completa e os resultados de
avaliacao (sintetica e contra o lab real).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

Path = Tuple[Any, ...]
_MISSING = object()

# path (ANTES de descer na lista) -> nome do campo-chave
# Ajustar por vendor/modelo YANG usado no seu parque.
SCHEMA_KEYS: Dict[Path, str] = {
    ("interface",): "name",
    ("interface", "*", "subinterface"): "index",
    ("network-instance",): "name",
    ("network-instance", "*", "protocols", "bgp", "neighbor"): "peer-address",
    ("network-instance", "*", "protocols", "ospf", "instance"): "name",
    ("network-instance", "*", "protocols", "ospf", "instance", "*", "area"): "area-id",
    ("acl", "ipv4-filter", "entry"): "sequence-id",
}

# listas cuja ORDEM dos elementos e semanticamente significativa
ORDERED_LISTS = {
    ("acl", "ipv4-filter", "entry"),
}

# leaf-lists que sao semanticamente CONJUNTOS -- reordenar nao e mudanca
UNORDERED_LEAF_LISTS = {
    ("network-instance", "*", "protocols", "bgp", "neighbor", "*", "import-policy"),
    ("network-instance", "*", "protocols", "bgp", "neighbor", "*", "export-policy"),
    ("network-instance", "*", "protocols", "bgp", "neighbor", "*", "community"),
}


@dataclass
class EditOp:
    op: str  # "added" | "removed" | "modified" | "reordered" | ...
    path: Path  # caminho legivel, com VALORES reais de chave
    tpath: Path  # caminho normalizado pelo esquema, com '*' p/ chaves
    old: Any = None
    new: Any = None


def diff_tree(desired: dict, observed: dict, path: Path = (), tpath: Path = ()) -> List[EditOp]:
    """Diff campo a campo entre dois subtrees dict-shaped."""
    ops: List[EditOp] = []
    keys = set(desired) | set(observed)
    for k in sorted(keys, key=str):
        d_child = desired.get(k, _MISSING)
        o_child = observed.get(k, _MISSING)
        cpath, ctpath = path + (k,), tpath + (k,)
        if d_child is _MISSING:
            ops.append(EditOp("added", cpath, ctpath, None, o_child))
        elif o_child is _MISSING:
            ops.append(EditOp("removed", cpath, ctpath, d_child, None))
        else:
            ops.extend(diff_value(d_child, o_child, cpath, ctpath))
    return ops


def diff_value(d_val, o_val, path, tpath) -> List[EditOp]:
    if isinstance(d_val, list) and isinstance(o_val, list):
        return diff_list(d_val, o_val, path, tpath)
    if isinstance(d_val, dict) and isinstance(o_val, dict):
        return diff_tree(d_val, o_val, path, tpath)
    if d_val != o_val:
        return [EditOp("modified", path, tpath, d_val, o_val)]
    return []


def diff_list(d_list, o_list, path, tpath) -> List[EditOp]:
    if tpath in SCHEMA_KEYS:
        key_field = SCHEMA_KEYS[tpath]
        return diff_keyed_list(d_list, o_list, path, tpath, key_field, ordered=tpath in ORDERED_LISTS)
    is_leaf_list = not d_list or not isinstance(d_list[0], dict)
    if is_leaf_list and (tpath in UNORDERED_LEAF_LISTS or tpath not in ORDERED_LISTS):
        return diff_set(d_list, o_list, path, tpath)
    return diff_sequence(d_list, o_list, path, tpath)


def diff_keyed_list(d_list, o_list, path, tpath, key_field, ordered) -> List[EditOp]:
    """Alinhamento por hash join, O(n) esperado -- em vez de busca O(n^3)."""
    ops: List[EditOp] = []
    d_map = {item[key_field]: item for item in d_list}
    o_map = {item[key_field]: item for item in o_list}
    d_keys, o_keys = set(d_map), set(o_map)

    for k in d_keys - o_keys:
        ops.append(EditOp("removed", path + (k,), tpath + ("*",), d_map[k], None))
    for k in o_keys - d_keys:
        ops.append(EditOp("added", path + (k,), tpath + ("*",), None, o_map[k]))
    for k in d_keys & o_keys:
        ops.extend(diff_tree(d_map[k], o_map[k], path + (k,), tpath + ("*",)))

    if ordered:
        d_order = [item[key_field] for item in d_list if item[key_field] in o_keys]
        o_order = [item[key_field] for item in o_list if item[key_field] in d_keys]
        if d_order != o_order:
            ops.append(EditOp("reordered", path, tpath, d_order, o_order))

    return ops


def diff_set(d_list, o_list, path, tpath) -> List[EditOp]:
    """Comparacao order-blind para leaf-lists semanticamente-conjunto."""
    d_set, o_set = set(d_list), set(o_list)
    if d_set != o_set:
        return [EditOp("modified", path, tpath, sorted(d_set, key=str), sorted(o_set, key=str))]
    return []


def diff_sequence(d_list, o_list, path, tpath) -> List[EditOp]:
    """Fallback: diff de sequencia via difflib.SequenceMatcher (Ratcliff/
    Obershelp, LCS-adjacente) -- usado so quando a lista nao e chaveavel
    nem declarada como conjunto. Raro em config de rede real."""
    ops: List[EditOp] = []
    sm = difflib.SequenceMatcher(a=d_list, b=o_list, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops.append(EditOp(tag, path, tpath, d_list[i1:i2], o_list[j1:j2]))
    return ops
