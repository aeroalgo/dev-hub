---
name: devops
description: "DEVOPS command pack — Docker, K8s/Helm, nginx/reverse-proxy, Ansible, Terraform/OpenTofu. Load when user says DEVOPS or asks for infra/ops work under that command."
---

# DEVOPS — pack loader

**Язык:** ответы пользователю — русский.

Это **не** BACK/FRONT lifecycle. Команда `DEVOPS` только подгружает скиллы из `.agents/skills/` (= `harness/skills/`) и помогает с инфраструктурой.

## Hot path при `DEVOPS …`

1. `OK DEVOPS` (+ тема из сообщения, если есть).
2. Выбери скиллы по таблице ниже (не грузи весь harness).
3. **Read** выбранные `.agents/skills/<name>/SKILL.md` целиком.
4. Делай задачу по этим скиллам. Fail-closed: без silent fallback.

## Pack (канон)

| Тема / ключевые слова | Скиллы (пути `.agents/skills/…/SKILL.md`) |
|-----------------------|-------------------------------------------|
| docker, compose, контейнер | [`docker-compose`](../docker-compose/SKILL.md), [`docker-management`](../docker-management/SKILL.md) |
| k8s, kubernetes, helm, kustomize | [`kubernetes`](../kubernetes/SKILL.md), [`kubernetes-ops`](../kubernetes-ops/SKILL.md), [`helm-charts`](../helm-charts/SKILL.md), [`kustomize`](../kustomize/SKILL.md) |
| nginx, proxy, tls, ssl, порт, firewall, lb | [`reverse-proxy`](../reverse-proxy/SKILL.md), [`ssl-tls-management`](../ssl-tls-management/SKILL.md), [`load-balancing`](../load-balancing/SKILL.md), [`firewall-config`](../firewall-config/SKILL.md) |
| ansible, сервер, пакеты, конфиг хоста | [`ansible`](../ansible/SKILL.md) |
| terraform, opentofu, iac, aws/gcp/azure infra | [`terraform`](../terraform/SKILL.md), [`opentofu-migration`](../opentofu-migration/SKILL.md), [`terraform-aws`](../terraform-aws/SKILL.md), [`terraform-gcp`](../terraform-gcp/SKILL.md), [`terraform-azure`](../terraform-azure/SKILL.md) |

Полный индекс с назначением каждого skill: [`docs/runbooks/devops-skills.md`](../../../docs/runbooks/devops-skills.md).

## Выбор по умолчанию

- `DEVOPS` **без** темы → Read этот файл + спроси одну тему **или** (если задача уже в сообщении) выбери строки таблицы по словам задачи.
- `DEVOPS docker nginx` → docker-* + reverse-proxy + ssl-tls-management + firewall-config (+ load-balancing при балансировке).
- Несколько тем → объедини наборы без дублей.

## FORBIDDEN

- Грузить все 16 скиллов пачкой без необходимости.
- Подменять BACK/FRONT/APP PLAN|IMPLEMENT|QA этим режимом.
- Писать `memory-bank/activeContext.md` из DEVOPS (нет role FINISH lifecycle).
