# loop/dag — DAG manifests (v2)

Production-ready DAG pipeline manifests for autonomous loop scheduling.

## Schema

Манифесты используют `loop-dag/v2`. Контракт реализован в `loop/dag.py` (`validate_manifest` и `_ALLOWED_*`).

Обязательные поля манифеста:

- `schema: "loop-dag/v2"`;
- `pipeline: {id: string}`;
- `source: {kind: "integration_gap" | "manifest", artifacts: [safe paths]}`;
- `execution: {autonomous: bool}`;
- `nodes: [...]`.

Обязательные поля узла:

- `id: string` — уникальный идентификатор узла в манифесте;
- `role: "BACK" | "FRONT" | "INTEG"`;
- `action: "implement" | "close"`;
- `completion: {type: "decompose" | "artifact"}`;
- `depends_on: string[]` — идентификаторы зависимых узлов;
- `decompose` — путь к `decompose-*/index.yaml`, если `completion.type=decompose`;
- `artifact` — путь к артефакту, если `completion.type=artifact`.

## `integ-demo.yaml`

[`integ-demo.yaml`](integ-demo.yaml) — канонический production-ready пример integration journey и шаблон для новых pipeline-манифестов. Он не запускает реальный portal pipeline: его задача — показать полный v2-контракт и порядок зависимостей.

Текущая цепочка состоит из четырёх узлов:

1. `gap_close` — `INTEG`, `artifact`, `close`; prerequisite для реализации;
2. `back_impl` — `BACK`, `decompose`, `implement`; зависит от `gap_close`;
3. `front_impl` — `FRONT`, `decompose`, `implement`; зависит от `gap_close`;
4. `integ_verify` — `INTEG`, `decompose`, `implement`; зависит от `back_impl` и `front_impl`.

Чтобы использовать манифест как шаблон:

1. скопируйте `integ-demo.yaml` в новый файл в этом каталоге;
2. задайте уникальный `pipeline.id`;
3. замените `source.artifacts` и пути completion-артефактов на безопасные пути своего pipeline;
4. сохраните уникальность `nodes[].id` и корректно укажите `depends_on`;
5. проверьте манифест через `validate_manifest` до передачи его runner.

Покрытие примера находится в `loop/tests/test_dag_manifest.py` и `loop/tests/test_dag_integ_journey.py`: тесты загружают YAML, проверяют `ok`, отсутствие циклов и уникальность идентификаторов, а также проходят полный порядок journey.

## Ограничения

- Пути `decompose` и `artifact` должны быть безопасными: абсолютные пути и сегменты `..` запрещены валидатором.
- Циклические зависимости и self-edge обнаруживаются через `validate_manifest`.
- Повторяющийся `node.id` выдаёт diagnostic `duplicate_node`.
- Узел можно запускать только после завершения всех узлов из `depends_on`; scheduler выполняет dependency-ready узлы последовательно и стабильно.
- Совместимый `loop-dag/v1` читается только через явный адаптер с диагностикой, а не через silent fallback.
- `integ-demo.yaml` — пример-контракт, а не production DAG конкретного portal; реальные pipeline должны иметь собственные существующие completion-артефакты.

Для общей operational semantics, checkpoint/recovery и rollout/rollback см. [`../README.md`](../README.md) и [`../WORKFLOW.md`](../WORKFLOW.md).
