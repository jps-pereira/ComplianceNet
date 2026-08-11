"""
config_parser.py -- parser de running-config -> dict compativel com host_vars.

Usa ntc-templates (TextFSM) para extrair campos estruturados da
running-config bruta por vendor. Ajustar VENDOR_MAP e os comandos por
plataforma conforme os NOS efetivamente suportados no seu parque.
"""
import re

from ntc_templates.parse import parse_output

VENDOR_MAP = {
    "vendor-a": "vendor_a_os",
    "vendor-b": "vendor_b_os",
    "vendor-c": "vendor_c_os",
    "vendor-d": "vendor_d_os",
}

NETCONF_DETECT_PATTERNS = {
    "vendor_a_os": r"netconf",
    "vendor_b_os": r"management\s+netconf",
    "vendor_c_os": r"netconf-yang",
    "vendor_d_os": r"netconf\s+ssh",
}


def parse_running_config(device_name: str, raw: str, platform: str) -> dict:
    ntc = VENDOR_MAP[platform]
    cmd_bgp = "show bgp summary"
    cmd_intf = "show interface" if "vendor_a" in ntc else "show interfaces"

    bgp_rows = parse_output(platform=ntc, command=cmd_bgp, data=raw)
    intf_rows = parse_output(platform=ntc, command=cmd_intf, data=raw)

    mgmt = next(
        (r["ip_address"] for r in intf_rows if "mgmt" in r.get("interface", "").lower()), ""
    )
    lo = next(
        (r["ip_address"] for r in intf_rows if "loopback" in r.get("interface", "").lower()), ""
    )

    return {
        "hostname": device_name,
        "mgmt_ip": mgmt.split("/")[0],
        "loopback_ip": lo.split("/")[0],
        "ospf_router_id": lo.split("/")[0],
        "platform": platform,
        "netconf_enabled": _detect_netconf(raw, ntc),
        "bgp_peers": [{"peer_ip": r["bgp_neigh"], "asn": r["remote_as"]} for r in bgp_rows],
        "acl_mgmt_permit": _parse_mgmt_acl(raw, ntc),
    }


def _detect_netconf(config: str, platform: str) -> bool:
    pattern = NETCONF_DETECT_PATTERNS.get(platform, "")
    return bool(re.search(pattern, config, re.IGNORECASE))


def _parse_mgmt_acl(config: str, platform: str) -> list:
    # Placeholder -- customizar extracao de CIDRs permitidos por vendor.
    return []
