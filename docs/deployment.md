# Implantação

Este documento descreve os requisitos de infraestrutura e os passos gerais para implantar o
ComplianceNet em um ambiente próprio. Valores específicos do ambiente de produção original
(IPs, hostnames, credenciais) **não** estão incluídos — use os placeholders indicados e
`config/templates/.env.example` como ponto de partida.

## Pré-requisitos de infraestrutura

### Servidor OOB

| Recurso | Produção (hardware real) | Laboratório virtual (ContainerLab) |
|---|---|---|
| SO | Ubuntu 22.04 LTS Server (amd64) | Ubuntu 22.04 LTS — KVM obrigatório |
| CPU | 4 vCPU/cores | 8 cores (topologia mínima) |
| RAM | 16 GB | 32 GB |
| Disco | 200 GB SSD | 300 GB SSD (imagens `.qcow2`) |
| KVM | Não necessário | Obrigatório para NOS baseados em VM |
| IP de gerência | IP fixo dedicado | IP fixo em bridge Docker interna |

Se os dispositivos físicos ainda não estiverem disponíveis, todo o pipeline pode ser desenvolvido
e validado com o [ContainerLab](https://containerlab.dev/), que expõe SSH e NETCONF de forma
idêntica ao hardware real. O Nokia SR Linux é recomendado como NOS de laboratório: é o `kind`
nativo do ContainerLab, a imagem é pública (`ghcr.io/nokia/srlinux`), tem NETCONF ativo por padrão
na porta 830 e não requer QEMU/vrnetlab.

### Acesso aos dispositivos

- SSH habilitado em todos os dispositivos, com usuário de serviço dedicado.
- NETCONF habilitado na porta 830 (nativo no Nokia SR Linux; requer configuração explícita em
  Juniper Junos e Cisco IOS-XE).
- Credenciais armazenadas exclusivamente em CI/CD Variables do GitLab (nunca em texto plano no
  repositório).

## Componentes a instalar

1. **Dependências base**: Docker (via repositório oficial — não usar `snap`, que quebra o
   ContainerLab), Terraform, Python 3 com virtualenv dedicado (`ansible`, `ansible-lint`,
   `napalm`, `ncclient`, `netmiko`, `pyang`, `yamllint`).
2. **GitLab CE** — via Docker Compose, hub central do pipeline (SCM, CI/CD, segredos,
   agendamentos).
3. **GitLab Runner** — executor dos jobs de CI/CD, com acesso direto aos dispositivos de rede.
4. **NetBox** — CMDB/IPAM, fonte da verdade do inventário.
5. **MinIO** — backend S3-compatível para o remote state do Terraform.
6. **(Opcional) ContainerLab** — laboratório virtual para desenvolvimento sem hardware físico.

Consulte a documentação oficial de cada projeto para os passos de instalação detalhados; os
arquivos em `config/templates/` deste repositório fornecem exemplos de configuração já adaptados
ao papel de cada componente no pipeline.

## Estrutura do repositório de configurações (`host_vars`)

O operador de rede interage apenas com o diretório `host_vars/` — um arquivo YAML por
dispositivo, com dados como IP de gerência, loopback, peers BGP e políticas de ACL de gerência.
Esse diretório é gerado e mantido automaticamente por `library/netbox_sync.py`: nunca deve ser
editado manualmente, pois qualquer arquivo criado fora do sync é sobrescrito na próxima execução.

```
network-oob/
├── host_vars/          # 1 arquivo YAML por device — único diretório editado manualmente
├── yang-models/        # modelos .yang por vendor (baixados dos repositórios oficiais)
├── netconf/            # payloads XML — caminho principal (netconf_enabled=true)
├── templates/          # templates Jinja2 — fallback apenas (netconf_enabled=false)
├── library/            # scripts de integração (este repositório)
├── playbooks/           # deploy, dry-run, rollback
├── inventory/           # inventário dinâmico do NetBox
├── terraform/           # IaC — sincroniza NetBox como código
└── .gitlab-ci.yml
```

## Variáveis de ambiente / segredos necessários

Ver `config/templates/.env.example`. Nunca commitar valores reais — todas as credenciais devem
ser configuradas como CI/CD Variables no GitLab, marcadas como `Masked` (senhas) e `Protected`
(variáveis de produção).

## Checklist de validação pós-implantação

- GitLab CE acessível e login funcional.
- `gitlab-runner verify` retorna `alive`.
- API do NetBox retorna JSON de dispositivos.
- Bucket do Terraform state visível no MinIO.
- `terraform plan` executa sem erros.
- Conectividade NETCONF testável via script Python simples (`get_config(source='running')`).
- `ansible all -m ping` retorna `pong` para o inventário dinâmico.
- Dry-run do pipeline exibe diff sem erros.
- Prometheus com todos os targets `UP`; dashboard Grafana carregado.
- syslog-ng recebendo logs dos dispositivos.
- Job de drift-detect: editar um device fora do pipeline e confirmar que um MR de drift é aberto
  automaticamente na próxima execução agendada.

## Fluxo de mudança padrão

1. Criar branch e editar `host_vars/<device>.yaml`.
2. Abrir Merge Request — pipeline de validação dispara automaticamente (lint + YANG).
3. Revisar e aprovar o merge para a branch principal.
4. Disparar manualmente o job de dry-run e revisar o diff exibido.
5. Disparar manualmente o job de deploy — Ansible aplica na ordem core → distribution → access,
   com commit-confirm e rollback automático em caso de perda de conectividade.
6. Confirmar métricas normais no Grafana e backup registrado no Git.
