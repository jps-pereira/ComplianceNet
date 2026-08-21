# ComplianceNet — Pipeline CI/CD para Redes

> Artefato de pesquisa. Este repositório documenta a **ferramenta** (o pipeline de CI/CD e os
> mecanismos de integração desenvolvidos pelos autores), não a réplica da infraestrutura
> privada em que ela foi originalmente implantada. IPs, hostnames, credenciais e demais dados
> específicos do ambiente de produção foram removidos ou substituídos por placeholders/templates.

# Selos Considerados
Os autores consideram o Selo de Artefatos Disponíveis (SeloD) para a avaliação. A estrutura desse diretório e a não reprodutibilidade da ferramenta se dão pela modalidade escolhida de código fechado, e também pelo própria natureza da ferramenta ser implementada de forma modularizada em servidor dedicado. A resposta dos tópicos posteriores advém justamente da opção de Código fechado de submissão, e da natureza da ferramenta. Os tópicos foram redigidos para satisfazer as instruções de submissão de README do CTA.

# Preocupações com segurança

O artefato disponibilizado neste repositório é restrito ao módulo SKSD (`library/sksd/`) e ao harness de avaliação com dados de amostra sintéticos/anonimizados. **O pipeline CI/CD completo, a topologia de rede real, credenciais de acesso a equipamentos e a instância de GitLab utilizada em produção não fazem parte deste artefato e não estão disponíveis no repositório.**

Não há risco de execução para os avaliadores: o código do SKSD é Python puro (stdlib apenas, sem chamadas de rede, sem I/O além de leitura de arquivos locais de amostra) e roda isoladamente, sem necessidade de acesso a qualquer equipamento real ou serviço externo. Os dados de configuração incluídos como amostra (`samples/` ou equivalente) são capturas anonimizadas — endereçamento IP, hostnames e identificadores de organização foram removidos ou substituídos por valores fictícios antes da inclusão no repositório.

Nenhuma credencial, chave SSH, token de API ou dado de rede real está presente no repositório ou é necessário para a execução do artefato.

# Instalação

O artefato requer apenas Python 3.x e a biblioteca padrão (stdlib) — não há dependências externas a instalar.

```bash
git clone <url-do-repositório>
cd <repositório>/library/sksd
python3 --version   # requer Python 3.8+
```

Não há etapa de build, compilação ou instalação de pacotes. Ao final deste processo, os módulos do SKSD já podem ser importados e executados diretamente.

# Teste mínimo

Este teste executa o SKSD contra um par de configurações de amostra (baseline vs. modificada) incluído no repositório, sem qualquer alteração no arquivo, e verifica que a saída do diff é gerada corretamente.

```bash
cd library/sksd
python3 -m ir_diff --baseline samples/ospf_baseline.xml --candidate samples/ospf_reordered.xml
```

**Resultado esperado:** a ferramenta deve reportar **nenhuma diferença semântica** entre os dois arquivos (`samples/ospf_reordered.xml` contém a mesma configuração OSPF do baseline, apenas com a lista de interfaces em ordem diferente). Esse é o comportamento que distingue o SKSD de um diff posicional — uma reordenação de lista sem mudança de conteúdo não deve gerar drift.

Tempo esperado: menos de 5 segundos. Recursos: desprezíveis (<50MB RAM).

# Experimentos

Esta seção reproduz o experimento multi-cenário apresentado no artigo, que compara o SKSD contra as 3 baselines (Naive-dict, Text-diff, Terraform-style) em 4 cenários de drift. Todos os arquivos de amostra usados abaixo estão incluídos em `library/sksd/samples/`.

**Ambiente**: Python 3.8+, stdlib apenas. Nenhum equipamento real, container ou serviço externo é necessário — os 4 cenários usam cópias em memória das capturas de amostra, com as perturbações sintéticas aplicadas pelo próprio script (mesma técnica usada no experimento original do artigo).

## Reivindicação #1 — ComplianceNet não gera falso-positivo em reordenação de lista, as baselines geram

**Comando:**
```bash
cd library/sksd
python3 multi_scenario_eval.py --scenario reorder --methods sksd,naive-dict,text-diff,terraform-style
```

**Configuração:** nenhuma alteração de arquivo necessária; o cenário usa os dados em `samples/ospf_baseline.xml` com reordenação aplicada em memória pelo próprio script (flag `--scenario reorder`).

**Tempo esperado:** < 10 segundos. **Recursos:** <100MB RAM, sem uso de disco além da leitura dos samples.

**Resultado esperado:** SKSD reporta 0 drifts (acerto); as 3 baselines (Naive-dict, Text-diff, Terraform-style) reportam drift onde não há mudança real (falso-positivo), reproduzindo a taxa relatada no artigo (SKSD 100% de acerto no cenário de reordenação; baselines 0%).

## Reivindicação #2 — ComplianceNet mantém acerto em cenários com mudança real (escalar e admin-state)

**Comando:**
```bash
python3 multi_scenario_eval.py --scenario router-id-change,no-change,admin-state-change --methods sksd,naive-dict,text-diff,terraform-style
```

**Configuração:** mesma base de dados de amostra; as perturbações (`router-id-change`, `admin-state-change`) e o cenário de controle (`no-change`) são aplicados em memória pelas flags do script.

**Tempo esperado:** < 15 segundos para os 3 cenários. **Recursos:** <100MB RAM.

**Resultado esperado:** os 4 métodos (SKSD e as 3 baselines) reportam corretamente a presença ou ausência de drift nesses 3 cenários — a comparação é justa e não favorece artificialmente o SKSD apenas no cenário de reordenação.

## O que é o ComplianceNet

O ComplianceNet é um pipeline de CI/CD para gestão de configuração de redes.multi-vendor. 
Ele resolve um problema comum em operação de rede: mudanças de configuração
aplicadas manualmente via SSH, sem validação prévia, sem histórico estruturado e sem rollback
automático, indisponibilidade por erro humano e ausência de governança. Ao resolver esse problema com uma
plataforma CI/CD, suge o problema de drift de configuração, que é a reivindicação principal da ferramenta.

O pipeline entrega:

- Controle de versão centralizado de configurações por dispositivo, grupo e camada de rede (Git).
- Validação sintática e de esquema (YANG) antes de qualquer mudança chegar ao equipamento.
- Deploy ordenado e controlado com dry-run e commit-confirm.
- Backup automatizado de configurações versionado em Git.
- Detecção de drift de configuração baseado em esqumas NETCONF/YANG `docs/architecture.md`, 
  que abre Merge Requests automáticos para revisão humana.

## Reivindicação vs. o que é infraestrutura de terceiros

Todos os módulos individuais usados (GitLab CE, NetBox, Terraform, Ansible, NAPALM, ncclient) são projetos open source de terceiros. 
A contribuição documentada neste repositório está nos **scripts de integração, configurações e mecanismos que conectam
esses módulos** e formam o pipeline proposto:

| Camada | Contribuição original (neste repo) |
|---|---|
| Sincronização de inventário | `library/netbox_sync.py` — gera `host_vars/` a partir do NetBox|
| Backup | `library/backup.py` — coleta `running-config` via NETCONF e versiona em Git |
| Detecção de drift | `library/drift_collector.py`, `drift_detector.py`, `config_parser.py` |
| Diff NETCONF Based | `library/sksd/` — alinhamento por chave de esquema YANG, evita falso-positivo por reordenação |
| Orquestração de deploy | `playbooks/` — dry-run e deploy com Ansible|
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
│   ├── architecture.md       # desenho do pipeline, stack, dispatch engine...
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
    └── metodo_netconf/
        ├── ir_diff.py
        ├── risk.py
        └── scheduler.py
```

## Licença

Este repositório é distribuído sob a licença Apache 2.0 (ver `LICENSE`). As
dependências (GitLab CE, NetBox, Terraform, Ansible, NAPALM etc.) mantêm suas próprias licenças.

## Status

Artefato de pesquisa referente a um MVP validado (ContainerLab, Nokia
SR Linux) e, parcialmente, em produção. Consulte `docs/architecture.md`, seção de limitações
conhecidas, para o escopo ainda não coberto.
