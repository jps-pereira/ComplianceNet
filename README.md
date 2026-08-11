# ComplianceNet — Pipeline CI/CD para Redes OOB Multi-Vendor

> Artefato de pesquisa. Este repositório documenta a **ferramenta** (o pipeline de CI/CD e os
> mecanismos de integração desenvolvidos pelos autores), não a réplica da infraestrutura
> privada em que ela foi originalmente implantada. IPs, hostnames, credenciais e demais dados
> específicos do ambiente de produção foram removidos ou substituídos por placeholders/templates.

# Selos Considerados
Os autores consideram o Selo de Artefatos Disponíveis (SeloD) para a avaliação.

## O que é o ComplianceNet

O ComplianceNet é um pipeline de CI/CD para gestão de configuração de redes *Out-of-Band* (OOB)
multi-vendor. Ele resolve um problema comum em operação de rede: mudanças de configuração
aplicadas manualmente via SSH, sem validação prévia, sem histórico estruturado e sem rollback
automático — o que gera drift de configuração, indisponibilidade por erro humano e ausência de
governança.

O pipeline entrega:

- Controle de versão centralizado de configurações por dispositivo, grupo e camada de rede (Git).
- Validação sintática e de esquema (YANG) antes de qualquer mudança chegar ao equipamento.
- Deploy ordenado e controlado (core → distribution → access) com dry-run e commit-confirm.
- Rollback automático em caso de falha (NAPALM commit-confirm, Git tags, Terraform state).
- Backup automatizado de configurações versionado em Git.
- Detecção de drift de configuração com um motor de diff semântico próprio (SKSD — ver
  `docs/architecture.md`), que abre Merge Requests automáticos para revisão humana.
- Observabilidade básica via Prometheus, Grafana e syslog centralizado.

## O que é contribuição original vs. o que é infraestrutura de terceiros

Todos os módulos individuais usados (GitLab CE, NetBox, Terraform, Ansible, NAPALM, ncclient,
Prometheus, Grafana etc.) são projetos open source de terceiros. A contribuição documentada
neste repositório está nos **scripts de integração, configurações e mecanismos que conectam
esses módulos** e formam o pipeline proposto:

| Camada | Contribuição original (neste repo) |
|---|---|
| Roteamento de protocolo | `library/dispatch.py` — decide NETCONF vs. CLI por device, consultando o NetBox |
| Sincronização de inventário | `library/netbox_sync.py` — gera `host_vars/` a partir do NetBox e abre MR automático |
| Backup | `library/backup.py` — coleta `running-config` via NETCONF e versiona em Git |
| Detecção de drift | `library/drift_collector.py`, `drift_detector.py`, `config_parser.py` |
| Diff semântico (SKSD) | `library/sksd/` — alinhamento por chave de esquema YANG, evita falso-positivo por reordenação |
| Orquestração de deploy | `playbooks/` — dry-run e deploy com Ansible, protocolo decidido pelo dispatch engine |
| Pipeline | `pipeline/.gitlab-ci.yml` — stages de validação, dry-run, deploy, backup e drift-detect |

Consulte `docs/architecture.md` para o desenho completo e `docs/deployment.md` para os requisitos
de infraestrutura necessários para uma eventual implantação (sem expor a infraestrutura privada
original).

## O que foi removido/generalizado

- Endereços IP reais de gerência, loopback e do servidor OOB → substituídos por placeholders
  (`<OOB_SERVER_IP>`, `<DEVICE_MGMT_IP>`, etc.) ou faixas de exemplo em RFC 5737/documentação.
- Nomes de dispositivos e sites reais (identificam localização física da rede) → substituídos por
  nomes genéricos (`AGG-01`, `CORE-01`, etc.) nos exemplos.
- Credenciais, tokens e senhas → nunca incluídos; usar variáveis de ambiente / CI-CD Variables
  (ver `config/templates/.env.example`).
- Detalhes de topologia física do parque de produção.

## Estrutura do repositório

```
compliancenet/
├── README.md
├── LICENSE
├── docs/
│   ├── architecture.md       # desenho do pipeline, stack, SKSD, dispatch engine
│   └── deployment.md         # pré-requisitos e passos de implantação (generalizados)
├── config/templates/         # exemplos de configuração — nunca valores reais
│   └── .env.example
├── pipeline/
│   └── .gitlab-ci.yml        # pipeline CI/CD sanitizado
├── playbooks/
│   ├── dry_run.yml
│   ├── deploy.yml
│   └── tasks/deploy_config.yml
└── library/                  # módulos Python de integração (contribuição original)
    ├── dispatch.py
    ├── netbox_sync.py
    ├── backup.py
    ├── drift_collector.py
    ├── drift_detector.py
    ├── config_parser.py
    └── sksd/
        ├── ir_diff.py
        ├── risk.py
        └── scheduler.py
```

## Licença

Este repositório é distribuído sob a licença Apache 2.0 (ver `LICENSE`). As
dependências (GitLab CE, NetBox, Terraform, Ansible, NAPALM etc.) mantêm suas próprias licenças.

## Status

Artefato de pesquisa referente a um MVP validado em ambiente de laboratório (ContainerLab, Nokia
SR Linux) e, parcialmente, em produção. Consulte `docs/architecture.md`, seção de limitações
conhecidas, para o escopo ainda não coberto (ex.: BGP e ACLs no motor de diff semântico).
