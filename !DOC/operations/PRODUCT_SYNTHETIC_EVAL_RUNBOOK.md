# Product Synthetic Eval Runbook

Last updated: 2026-04-22  
Scope: live synthetic evaluation of the `chat_v2` product loop

## Зачем

Этот прогон нужен, чтобы мерить не качество STT само по себе, а качество продукта на уровне бизнес-логики:

- правильно ли определяется карьерный контекст
- уводим ли мы пользователя в `first useful mission`, а не в лишний baseline-loop
- сохраняется ли `embedded_first_mission` baseline
- пишется ли `session_evidence`
- возвращается ли snapshot в состояние `ready_for_program`

Логика простая:

- пока moat и бизнес-петля ещё шлифуются, основной eval должен быть `text-level`
- голос здесь только транспорт и источник транскрипта
- voice/STT benchmark живёт отдельно в `STT_BENCHMARK_RUNBOOK.md`

## Инструмент

Основной live-runner:

- [scripts/run_product_synthetic_eval.py](../../scripts/run_product_synthetic_eval.py)

Текущие synthetic set'ы:

- `mainline`
- `expanded`

`mainline` включает:

- `workplace_first_value`
- `interview_first_value`
- `project_first_value`

`expanded` добавляет более вариативные профили:

- `workplace_status_update`
- `project_tradeoff_story`
- `interview_self_intro_gap`

## Что проверяется

Для каждого сценария runner проверяет:

- был ли completion signal
- completion signal считается валидным, если пришёл либо `session_complete`, либо farewell transcript с `phase=session_end`
- был ли handoff в `first useful mission`
- совпал ли `primary_context`
- совпал ли `recommended_track`
- вернулся ли snapshot в `setup.state = ready_for_program`
- записался ли `assessment.source = embedded_first_mission`
- сохранился ли `session_evidence.latest`
- совпал ли `session_evidence.latest.task_type`

Результат по сценарию:

- `PASS/FAIL`
- `score` в процентах
- список отдельных `checks`
- короткий `snapshot_excerpt`
- `event_tail`

## Как запускать

Mainline baseline:

```bash
python scripts/run_product_synthetic_eval.py \
  --base-url http://127.0.0.1:8000 \
  --output product-synthetic-baseline-report.json
```

Expanded regression run:

```bash
python scripts/run_product_synthetic_eval.py \
  --base-url http://127.0.0.1:8000 \
  --scenario-set expanded \
  --output product-synthetic-expanded-report.json
```

Один конкретный сценарий:

```bash
python scripts/run_product_synthetic_eval.py \
  --base-url http://127.0.0.1:8000 \
  --scenario workplace_first_value
```

Recommended Windows local run:

```powershell
venv\Scripts\python.exe main.py
venv\Scripts\python.exe scripts/test_voice_backend.py
venv\Scripts\python.exe scripts/run_product_synthetic_eval.py --base-url http://127.0.0.1:8000 --scenario-set mainline --turn-timeout 20 --session-timeout 30
```

Timeout guidance:

- synthetic eval measures the product loop, not raw provider latency
- with a remote/corporate LLM backend, `8s` can produce false runtime failures even when the service logic is correct
- local truth-run default should be treated as `turn-timeout=20`, `session-timeout=30`
- active local/team LLM truth-state: `VLLM_BASE_URL=http://192.168.0.18:8000/v1`, `VLLM_API_KEY=token-abc123`

## Как читать результат

Сначала смотрим на:

- `average_score`
- `pass_rate`

Потом по каждому сценарию:

- если падает `first_useful_mission_handoff`, продукт снова утащил пользователя в лишний setup-loop
- если падает `assessment_source`, embedded baseline не записался или был затёрт
- если падает `latest_evidence_task_type`, runtime и persisted product state расходятся
- если падает `primary_context` или `recommended_track`, пользователь пошёл не в тот карьерный контур
- если падает `completion_signal_seen`, flow завершения стал нестабильным

## Рабочий порядок

Когда меняется product loop:

1. Прогоняем `run_product_synthetic_eval.py`
2. Смотрим, улучшился или ухудшился `average_score`
3. Разбираем красные сценарии как продуктовые баги, а не как случайные LLM-ответы
4. Только потом идём в live browser smoke
5. И только после стабилизации бизнес-логики углубляемся в STT/TTS/voice UX

## Связанные runbook'и

- [VOICE_OBSERVABILITY_RUNBOOK.md](./VOICE_OBSERVABILITY_RUNBOOK.md)
- [STT_BENCHMARK_RUNBOOK.md](./STT_BENCHMARK_RUNBOOK.md)
