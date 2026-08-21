# ComplianceNet — Pipeline CI/CD para Redes

> Artefato de pesquisa. Este repositório documenta a **ferramenta** (o pipeline de CI/CD e os
> mecanismos de integração desenvolvidos pelos autores), não a réplica da infraestrutura
> privada em que ela foi originalmente implantada. IPs, hostnames, credenciais e demais dados
> específicos do ambiente de produção foram removidos ou substituídos por placeholders/templates.

# Selos Considerados
Os autores consideram o Selo de Artefatos Disponíveis (SeloD) para a avaliação. A estrutura desse diretório e a não reprodutibilidade da ferramenta se dão pela modalidade escolhida de código fechado, e também pelo própria natureza da ferramenta ser implementada de forma modularizada em servidor dedicado. A resposta dos tópicos posteriores advém justamente da opção de Código fechado de submissão, e da natureza da ferramenta. Os tópicos foram redigidos para satisfazer as instruções de submissão de README do CTA.

# Preocupações com segurança

O código-fonte deste projeto — pipeline CI/CD e o módulo de diff semântico (SKSD) — **não é disponibilizado** neste artefato. A ferramenta está integrada a uma infraestrutura de rede em produção: dez dispositivos de rede reais, uma instância de GitLab self-hosted sem TLS, integração com NetBox/Terraform, e credenciais operacionais de acesso aos equipamentos. A divulgação do código completo, mesmo com anonimização, exporia detalhes de topologia e práticas operacionais dessa rede.

Como consequência, **não há execução de código pelo avaliador em nenhuma etapa** — logo, não há risco de segurança a ser mitigado, pois nada roda no ambiente do revisor. A avaliação deste artefato se baseia inteiramente na documentação dos processos e dos resultados experimentais apresentados abaixo, e não na execução direta da ferramenta.

# Instalação

Não há pacote instalável fornecido aos avaliadores. Esta seção documenta, para fins de transparência sobre o ambiente em que a ferramenta foi de fato construída e testada, os componentes envolvidos:

- **Módulo SKSD**: Python 3.x, apenas biblioteca padrão (sem dependências externas) — seis módulos internos (`ir_diff.py`, `risk.py`, `baselines.py`, `terraform_style_baseline.py`, `ospf_tree_adapter.py`, `xml_adapter.py`).
- **Pipeline**: GitLab CI/CD (self-hosted, HTTP interno), ContainerLab para simulação de topologia (Nokia SR Linux), NETCONF/ncclient para coleta e aplicação de configuração, NetBox como fonte de verdade de inventário via Terraform.
- **Ambiente de validação real**: 10 dispositivos de rede de uma topologia OOB real (8x agregação, 1x core, 1x laboratório), usados nos experimentos descritos abaixo.

Essa descrição serve apenas para contextualizar os resultados relatados no artigo — não constitui um roteiro de instalação reproduzível pelo avaliador.

# Teste mínimo

Não é oferecido um teste mínimo executável pelo avaliador, pela mesma razão exposta acima: o código não é distribuído. Em vez disso, descrevemos aqui o comportamento observável da ferramenta, tal como testado pelos autores, para dar ao avaliador uma noção concreta da funcionalidade sem exigir execução:

Ao rodar o SKSD sobre duas capturas de configuração de um mesmo dispositivo — uma servindo de baseline e outra com a lista de interfaces reordenada mas sem nenhuma mudança de conteúdo — o SKSD reporta corretamente **zero drift**, pois o algoritmo indexa listas pela chave semântica do schema YANG (ex: nome da interface), não pela posição. Esse é o comportamento mínimo que diferencia o SKSD de uma ferramenta de diff textual ou posicional, e foi verificado manualmente pelos autores contra os 10 dispositivos reais do laboratório, sem nenhum falso-positivo.

# Experimentos

Esta seção documenta as principais reivindicações do artigo e os resultados efetivamente obtidos pelos autores. Como o código não é disponibilizado, o avaliador não poderá reexecutar os experimentos — o objetivo aqui é apresentar a metodologia com detalhe suficiente para que a reivindicação seja auditável por inspeção (isto é, para que o avaliador julgue a plausibilidade e o rigor do experimento a partir da descrição, mesmo sem rodar o código).

## Reivindicação #1 — SKSD elimina falsos-positivos em reordenação de listas, ao contrário das baselines

**Metodologia:** os autores definiram 4 cenários de drift — (i) reordenação da lista de interfaces OSPF sem mudança de conteúdo, (ii) mudança de um valor escalar (router-id), (iii) cenário de controle sem nenhuma mudança, (iv) mudança de admin-state de uma interface. Cada cenário foi executado contra os 10 dispositivos reais do laboratório, comparando 4 métodos de diff: SKSD, Naive-dict, Text-diff e Terraform-style. As perturbações sintéticas (mudança de router-id, inversão de admin-state) foram aplicadas sobre cópias em memória da configuração observada — nunca no equipamento real — técnica também usada e divulgada no cenário de reordenação original.

**Resultado obtido:** o SKSD acertou 100% dos casos nos 4 cenários. As 3 baselines acertaram 100% nos cenários (ii), (iii) e (iv), mas falharam completamente (0% de acerto, ou seja, reportaram falso-positivo de drift) no cenário (i) de reordenação — exatamente o caso que o SKSD foi desenhado para tratar corretamente. A comparação foi desenhada para ser justa: as baselines não perdem em todos os cenários, só no que expõe sua limitação estrutural (comparação posicional).

## Reivindicação #2 — A vantagem do SKSD é de corretude, não de desempenho

**Metodologia:** medição de tempo isolada à função de comparação de cada método (excluindo o tempo de coleta via NETCONF), com 30 repetições × 10 dispositivos = 300 amostras por célula (4.800 amostras no total, cobrindo os 4 cenários × 4 métodos), agregadas com intervalo de confiança via distribuição t de Student.

**Resultado obtido:** o SKSD **não** é o método mais rápido — o Terraform-style geralmente venceu em tempo de execução, e o Text-diff foi consistentemente o mais lento dos 4 (por serializar para JSON antes de comparar). Um outlier foi identificado e investigado: a célula Terraform-style/mudança-de-router-id apresentou um intervalo de confiança 5x mais largo que o esperado; isolando a causa, tratava-se de uma única amostra de 2,92ms (entre 300) atribuída a uma interrupção do sistema operacional em um dispositivo específico — ao remover esse outlier, a célula ficou consistente com a célula equivalente do cenário de reordenação, confirmando que não é um comportamento do algoritmo. Os autores reportam esse resultado de forma direta no artigo: o argumento em favor do SKSD é sobre corretude semântica, não sobre velocidade.

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
