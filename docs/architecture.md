# Arquitetura

## Visão geral

O pipeline roda sobre um servidor Linux dedicado dentro da própria rede OOB, que hospeda GitLab
CE (SCM + CI/CD), NetBox (CMDB/IPAM — fonte da verdade), MinIO (remote state do Terraform) e a
stack de observabilidade (Prometheus, Grafana, syslog-ng). A comunicação com os dispositivos
gerenciados ocorre via NETCONF (caminho principal) ou SSH/CLI (fallback), decidida
automaticamente por device.

## Fluxo do pipeline

Regra de ouro: nenhuma configuração chega a um dispositivo de produção sem antes passar por
(1) lint sintático + validação YANG, (2) aprovação humana via Merge Request, e (3) dry-run no
próprio equipamento.

| Etapa | Descrição |
|---|---|
| 1 — Push/MR | Engenheiro abre Merge Request com alteração de config (`host_vars/*.yaml`) ou IaC |
| 2 — CI lint/YANG | `yamllint` + `ansible-lint` + `terraform validate` + `pyang` (valida modelos YANG) |
| 3 — Aprovação humana | Review obrigatório antes do merge |
| 4 — CD dry-run | Diff exibido sem aplicar (NETCONF get-config ou NAPALM dry-run) |
| 5 — CD apply | NAPALM/NETCONF conecta no equipamento real e aplica com commit-confirm |
| 6 — Ansible orquestra deploy na ordem core → distribution → access | |
| 7 — Backup | Coleta periódica de `running-config` via NETCONF, versionada em Git |
| 8 — Rollback | Se falhar: commit-confirm reverte automaticamente; Git tag / Terraform state restauram IaC |

## Stack de ferramentas (100% open source, de terceiros)

| Camada | Ferramenta |
|---|---|
| SCM / CI/CD | GitLab CE (self-hosted) |
| CMDB / IPAM | NetBox |
| Remote state | MinIO (S3-compatível) |
| IaC | Terraform (sincroniza estado do NetBox como código — não gerencia config dos switches) |
| Lint / validação | yamllint, ansible-lint, pyang |
| Orquestração de deploy | Ansible |
| Abstração multi-vendor | NAPALM, ncclient (NETCONF), Netmiko (fallback SSH/CLI) |

## Sincronização de inventário (NetBox → Git)

O NetBox é a única fonte da verdade para o inventário. `library/netbox_sync.py` consulta a API do
NetBox, gera um arquivo YAML por device ativo em `host_vars/` e abre um Merge Request automático
com as mudanças — nunca escreve direto na branch principal. Remover um device do pipeline é feito
mudando seu status para `inactive` no NetBox; o sync remove o `host_vars/` correspondente e abre
um MR de remoção.

## Backup

`library/backup.py` coleta a `running-config` de cada device via NETCONF (`ncclient`) e versiona
em um repositório Git dedicado, com commit apenas quando há mudança real (idempotente). É
importante notar a distinção entre **estado observado** (o que o backup coleta) e **estado
desejado** (o que está declarado em `host_vars/`) — um device pode ter configuração real nunca
expressa como intenção no Git. O módulo de detecção de drift existe justamente para fechar essa
lacuna.

## Detecção de drift

Quando alguém aplica uma mudança diretamente em um equipamento (fora do pipeline), o job
`drift-detect` (agendado ou disparado por webhook) coleta a config real via NETCONF
(`drift_collector.py`), converte para o formato de `host_vars` (`config_parser.py`) e compara com
o estado desejado no Git (`drift_detector.py`). Se houver divergência, abre um Merge Request com o
diff para decisão humana explícita: aceitar o drift (merge) ou reverter o equipamento.

Uma comparação ingênua (dicionário posicional ou diff de texto) gera falso-positivo sempre que um
dispositivo retorna a mesma configuração em ordem diferente entre duas coletas — comum em
listas YANG sem ordenação semântica (ex.: peers BGP, interfaces). O **SKSD** (`library/sksd/`)
resolve isso explorando a estrutura já declarada no esquema YANG do dispositivo:

- Listas com chave declarada (YANG `list` + `key`, ex.: nome de interface, endereço de peer BGP)
  são alinhadas por chave via hash join — O(n) — em vez de por posição.
- Leaf-lists sem ordenação semântica (ex.: políticas de import/export BGP) são comparadas como
  conjunto.
- Listas onde a ordem importa (ex.: entradas de ACL, onde a posição determina precedência) usam
  diff de sequência (`difflib.SequenceMatcher`), preservando reordenação como mudança real.

Cada operação de diff recebe um peso de risco (0–100) por casamento de prefixo mais longo contra
uma tabela indexada pelo caminho normalizado do esquema (`library/sksd/risk.py`), determinando
prioridade e número de revisores exigidos no MR — nunca se o MR é necessário ou não.

### Limitações conhecidas

- `SCHEMA_KEYS` é escrito manualmente por vendor; não há descoberta automática de chaves a partir
  do módulo `.yang` — item de trabalho futuro.
- Cobertura de validação real: interfaces, OSPF e VLAN. BGP, ACLs e outras seções do schema YANG
  ainda não têm configuração real aplicada em laboratório para exercitar o SKSD.
- Os pesos de `RISK_WEIGHTS` são julgamento de engenharia, não calibrados contra incidentes reais
  de produção.

## Roadmap

- Automatizar o fluxo `discover_devices.py → generate_tfvars.py → terraform apply` (hoje manual)
  como job agendado, no mesmo padrão do `drift-detect`.
- Avaliar NetBox Discovery/Diode para discovery contínuo caso o parque cresça ou drivers para
  outros vendors sejam necessários.
- Policy as Code (OPA/Rego), log aggregation (Grafana Loki), telemetria gNMI, UI Ansible (AWX),
  paralelismo (Nornir).
- Integração via MCP (Model Context Protocol): expor GitLab, NetBox, Terraform e Prometheus como
  tools para um agente Claude operar o pipeline com gates de aprovação humana explícitos —
  ver seção de segurança abaixo antes de considerar essa integração.

## Princípios de segurança para automação com agentes (se/quando adotada)

Caso o pipeline seja estendido para permitir que um agente (ex.: via MCP) opere sobre ele:
tools destrutivas sempre exigem aprovação humana explícita, cada chamada é auditada, os
servidores de integração ficam isolados na rede interna (nunca expostos publicamente), leitura é
liberada por padrão e escrita exige confirmação, com rate limiting e timeout por operação.
