# DEVOPS skills

Канонический индекс infra-skills для команды `DEVOPS`. Все ссылки ведут на
реальные файлы `harness/skills/*/SKILL.md`; в проекте они доступны также через
`.agents/skills/` (symlink на `harness/skills/`).

## Docker

| Skill | Когда загружать |
|---|---|
| [docker-compose](../../harness/skills/docker-compose/SKILL.md) | Compose-стек, зависимости сервисов, сети и volumes |
| [docker-management](../../harness/skills/docker-management/SKILL.md) | Dockerfile, образы, lifecycle контейнеров и диагностика |

## Kubernetes

| Skill | Когда загружать |
|---|---|
| [kubernetes](../../harness/skills/kubernetes/SKILL.md) | Pods, Deployments, Services, Ingress и `kubectl` |
| [kubernetes-ops](../../harness/skills/kubernetes-ops/SKILL.md) | Эксплуатация, масштабирование и troubleshooting workload’ов |
| [helm-charts](../../harness/skills/helm-charts/SKILL.md) | Helm charts, values, releases и repositories |
| [kustomize](../../harness/skills/kustomize/SKILL.md) | Declarative overlays и patching Kubernetes manifests |

## Edge, сеть и безопасность

| Skill | Когда загружать |
|---|---|
| [reverse-proxy](../../harness/skills/reverse-proxy/SKILL.md) | nginx/Traefik, маршрутизация, TLS termination и gateway |
| [ssl-tls-management](../../harness/skills/ssl-tls-management/SKILL.md) | Сертификаты, HTTPS, renewal и TLS-аудит |
| [load-balancing](../../harness/skills/load-balancing/SKILL.md) | Балансировка, health checks и traffic shifting |
| [firewall-config](../../harness/skills/firewall-config/SKILL.md) | iptables/nftables и cloud firewall |

## Хосты и автоматизация

| Skill | Когда загружать |
|---|---|
| [ansible](../../harness/skills/ansible/SKILL.md) | Playbook, roles, inventory и управление хостом |

## Infrastructure as Code

| Skill | Когда загружать |
|---|---|
| [terraform](../../harness/skills/terraform/SKILL.md) | Terraform providers, modules, state и ресурсы |
| [opentofu-migration](../../harness/skills/opentofu-migration/SKILL.md) | Миграция Terraform → OpenTofu и CI/CD |
| [terraform-aws](../../harness/skills/terraform-aws/SKILL.md) | AWS-инфраструктура через Terraform |
| [terraform-gcp](../../harness/skills/terraform-gcp/SKILL.md) | GCP-инфраструктура через Terraform |
| [terraform-azure](../../harness/skills/terraform-azure/SKILL.md) | Azure-инфраструктура через Terraform |

## Правило выбора

Агент загружает только skills из соответствующей строки pack, читает каждый
выбранный `SKILL.md` целиком и не использует неявный fallback. Команда `DEVOPS`
без темы выбирает тему из задачи; если темы нет, запрашивает её.
