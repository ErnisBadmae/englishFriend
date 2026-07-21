# Article → Interview Mission: проектное решение

Last updated: 2026-07-17
Status: design proposal, ждёт подтверждения владельца продукта (код не написан)
Задание: [FABLE_TASK_ARTICLE_TO_INTERVIEW_MISSION.md](./FABLE_TASK_ARTICLE_TO_INTERVIEW_MISSION.md)

## 1. Вердикт

**Сначала проверить вручную, затем строить узкий срез.**

- Тренировочная половина гипотезы (статья → пакет практики → текстовая сессия → evidence → следующая миссия) — это не новый продукт, а усиление существующего цикла. В коде уже есть её маленькая версия: `set_project_notes` → `project_story_pack` (`app/services/learning_plan_service.py:430`, `app/api/career.py:91`) плюс slot-flow `technical_project_walkthrough`.
- Публикационная половина (LinkedIn) — единственное место, где живёт риск «второго продукта». Она сводится к **статусу готовности фрагмента**, а не к функции публикации. Никакого редактора, переводчика и «раздела статей» не появляется.
- `CURRENT_PRODUCT_STATE.md` фиксирует: первый founder typed/composer run базового цикла ещё не проведён. Строить надстройку над непроверенным циклом преждевременно, поэтому этап 0 (ручная проверка на существующей миссии) — это ворота, а не формальность.

## 2. Ценность для основного карьерного цикла

Wedge цикла — `CareerProfile -> VacancyContext -> Mission -> text session -> Evidence -> Next Mission`. Статья о grounded-judge-gate — это готовый, реальный `project_walkthrough`-материал: собственный проект, метрика, инвариант, ограничения, trade-off'ы. Ровно то, что `technical_project_walkthrough` сейчас пытается вытащить из пользователя вслепую.

Что добавляет материал к циклу:

- миссия получает **конкретное содержание** вместо абстрактного «расскажи о проекте» — вопросы интервьюера и слоты привязаны к реальным утверждениям, которые автор обязан уметь защищать;
- evidence становится **проверяемым по покрытию**: «какие утверждения статьи раскрыты, какие пропущены» — наблюдаемый сигнал, которого сейчас нет;
- LinkedIn-статус даёт **честную внешнюю мотивацию возврата** (Gate 3 воркплана: return reason) — «фрагмент 2 ещё не отрепетирован» и есть причина для session 2.

Это не создаёт параллельный цикл: материал — это источник контента для той же цепочки Mission → Evidence → Next Mission.

## 3. Решение reuse / extend / new mission

**Выбор: extend — один новый узкий `task_type` поверх существующей mission-anchored механики, без нового движка.**

| Вариант | Оценка |
| --- | --- |
| 1. Чистый reuse `technical_project_walkthrough` | Слоты (problem/approach/metric/impact) подходят, но миссия ничего не знает о карте утверждений, evidence не может зафиксировать покрытие, промпт не может нести правила «источник — недоверенные данные» и «уровень A2–B1». Годится только для этапа 0. |
| 2. **Extend: новый `task_type = source_material_walkthrough`**, переиспользующий контракт слотов walkthrough, mission-anchored runtime, `session_evidence`, `recommend_next_mission` | Выбран. Кодовая база уже растёт именно так: `TECHNICAL_MISSION_SPECS` в `learning.py` — шесть записей одинаковой формы, добавление седьмой дёшево. |
| 3. Новый тип миссии с динамическими слотами из claim map | Правильная конечная форма, но требует фабрики контрактов вместо статического реестра `MISSION_CONTRACTS`. Откладывается: в v1 покрытие утверждений считается детерминированно на этапе evidence, а не слотами в реальном времени. |
| 4. Ничего не строить | Частично принят: этап 0 — ручная проверка ценности без кода. Но правило готовности публикации без кода непроверяемо в принципе, поэтому «совсем ничего» не закрывает гипотезу. |

## 4. Схема потока

```text
Markdown собственной статьи (вставка, без URL)
  -> POST /api/v1/career/{user_id}/source-material
     [дет.] лимит длины / выбор раздела, sha256, подтверждение авторства
     [LLM]  кандидат пакета практики (JSON)
     [дет.] валидация пакета: каждое утверждение несёт verbatim-цитату,
            цитата обязана быть подстрокой источника; иначе утверждение отбрасывается
  -> roadmap["source_materials"] (PostgreSQL, LearningPlan.roadmap)
  -> ProgramSnapshot:材料 + статусы фрагментов + рекомендация миссии
  -> Mission: source_material_walkthrough (mission-anchored, text session)
     [LLM]  коучинг-ходы, по одному вопросу, русская помощь коротко
     [дет.] slot scaffold (существующий plan_mission_turn)
  -> session_end -> persist_session_evidence_if_needed
     [дет.] claims_covered / claims_missed, target_phrases_used,
            anti-copy проверка, счётчик блокирующих ошибок
  -> [дет.] правило готовности фрагмента (draft -> rehearsed -> ready)
  -> [дет.] recommend_next_mission: repeat на самом важном пропущенном
            утверждении или advance
```

## 5. Минимальные доменные контракты

Всё живёт в `LearningPlan.roadmap` (JSONB, PostgreSQL — канон), как `vacancy_text`, `project_story_pack`, `session_evidence`. Ни одной новой таблицы.

### 5.1 `roadmap["source_materials"]` — список, в v1 один активный элемент

```json
{
  "material_id": "mat-<uuid>",
  "title": "LLM-судья ошибается, а тесты остаются зелёными",
  "content_sha256": "<hash нормализованного источника>",
  "source_chars": 11840,
  "selected_section": null,
  "authorship_confirmed": true,
  "created_at": "2026-07-17T...",
  "pack_version": 1,
  "source_text": "<нормализованный текст, только принятый объём>",
  "pack": {
    "claims": [
      {
        "id": "claim-1",
        "statement_ru": "...",
        "statement_en_simple": "...",
        "source_quote": "<verbatim-подстрока источника>",
        "key_terms": ["manual review", "extracted value"],
        "kind": "core | limitation | tradeoff"
      }
    ],
    "simple_retell_en": "<пересказ на 60–90 сек, короткие предложения>",
    "target_phrases": ["deterministic check", "..."],
    "interviewer_questions": [
      {"audience": "recruiter | technical", "question_en": "...", "claim_ids": ["claim-1"]}
    ],
    "contested_points": [{"claim_id": "claim-3", "challenge_en": "..."}],
    "linkedin_fragments": [
      {
        "fragment_id": "frag-1",
        "text_en": "...",
        "claim_ids": ["claim-1", "claim-2"],
        "status": "draft"
      }
    ]
  }
}
```

Происхождение и версия: `content_sha256` + `pack_version`. Повторная вставка изменённой статьи = новый material с новым hash; старые evidence остаются привязанными к старому `material_id`. Материал после приёма неизменяем — «потеря происхождения» (риск 7) закрыта конструктивно.

### 5.2 Расширение `session_evidence` (не ломающее)

Evidence — schemaless dict внутри roadmap; существующие потребители читают по ключам. Для `task_type = source_material_walkthrough` добавляются только новые опциональные поля:

```json
{
  "task_type": "source_material_walkthrough",
  "material_id": "mat-...",
  "material_sha256": "...",
  "claims_covered": ["claim-1", "claim-2"],
  "claims_missed": ["claim-3"],
  "target_phrases_used": ["manual review"],
  "raw_answer": "<лучший сырой ответ пользователя, verbatim>",
  "corrected_answer": "<recast коуча для повторного использования>",
  "copy_similarity": 0.18,
  "self_built_answer": true,
  "blocking_error_count": 1,
  "fragment_readiness": [{"fragment_id": "frag-1", "status": "rehearsed", "reason": "claim-3 not yet defended"}]
}
```

Существующие поля (`summary`, `main_issue`, `weakness_tags`, `outcome_score`, `next_focus`) заполняются как раньше — snapshot, `build_reusable_answers`, `_detect_repeat_vs_advance` продолжают работать без изменений.

### 5.3 Состояние агента

Новых ключей `AgentState` **не требуется**: пакет (обрезанный до бюджета) передаётся через уже объявленный `mission_memory_context` (`app/agent/state.py:127`). Guard-тест схемы не тронут.

## 6. Точки встраивания (файлы / функции)

| Место | Изменение |
| --- | --- |
| `app/api/career.py` | новый POST `/{user_id}/source-material` (+ GET статуса), зеркало `submit_project_notes` |
| `app/services/source_material_service.py` (новый, узкий) | приём источника, лимит длины, hash, вызов LLM через `get_llm_provider()`, детерминированные валидаторы пакета, правило готовности фрагмента, подсчёт покрытия |
| `app/services/learning_plan_service.py` | `set_source_material` / `get_source_materials` (по образцу `set_project_notes`); ветка в `_build_session_evidence` для нового task_type |
| `app/services/missions/contracts.py` | регистрация контракта `source_material_walkthrough` (те же 4 слота walkthrough в v1) в `MISSION_CONTRACTS` |
| `app/agent/nodes_v2/learning.py` | task_type в `MISSION_ANCHORED_TASK_TYPES`; spec-запись + материал-aware промпт (данные из `mission_memory_context`) |
| `app/services/program_snapshot_service.py` | ветка в `recommend_next_mission`: активный материал с непокрытыми утверждениями → миссия по самому важному пропущенному claim; секция `source_materials` в snapshot |
| `app/services/voice_session/persistence.py` + `conversation_runtime/controller.py` | прокинуть material-контекст в `persist_session_evidence_if_needed` (один опциональный параметр) |
| `frontend/` | минимум: экран вставки материала + статусы фрагментов на home; рендер backend-состояния, никакой своей логики |

## 7. Изменения API и интерфейса

- `POST /api/v1/career/{user_id}/source-material` — вход: `markdown_text`, опционально `selected_section`, `authorship_confirmed: true` (обязателен), опционально `target_role_note`. Выход: material_id, счётчики (claims, fragments), отклонённые утверждения с причиной.
- `GET` — статус материалa и фрагментов (или просто внутри ProgramSnapshot; предпочтительно snapshot, без нового GET).
- Публикации из продукта нет вообще: пользователь копирует «ready»-фрагмент руками.

## 8. Граница детерминированного кода и LLM

Схема сознательно повторяет паттерн самой статьи: LLM зажата между детерминированными проверками.

**LLM (через существующий порт `get_llm_provider()`):**
- генерация кандидата пакета (structured JSON);
- коучинг-ходы в сессии (существующий learning node);
- субъективный комментарий качества ответа — помечен `subjective`, ни на один статус не влияет.

**Детерминированный код (право вето):**
- приём источника: лимит длины, hash, подтверждение авторства;
- валидация пакета: `source_quote` каждого утверждения обязан быть подстрокой нормализованного источника, иначе утверждение отбрасывается (и логируется); фрагмент без валидных claim_ids не создаётся;
- покрытие утверждений: сопоставление `key_terms`/цитат с user-turns;
- anti-copy: n-gram overlap ответа пользователя с `simple_retell_en` и `linkedin_fragments`;
- правило готовности фрагмента и выбор следующей миссии.

## 9. Удержание английского на уровне пользователя

- Промпт генерации пакета получает `language_level` из state и требование «короткие предложения, простые конструкции» (тот же принцип уже зафиксирован в реальном `LINKEDIN_POSTS.md`).
- Детерминированный пост-чек `simple_retell_en` и фрагментов: средняя длина предложения ≤ 14 слов, максимум ≤ 20; нарушение → регенерация один раз → при повторном нарушении фрагмент помечается `needs_simplification` и не может стать `ready`.
- Главный структурный guard — само правило готовности: C1-формулировка, которую пользователь не может защитить своими словами, никогда не пройдёт порог покрытия + anti-copy, то есть никогда не станет `ready`. Имитация уровня не запрещается лозунгом — она не проходит ворота.

## 10. Контракт доказательств и правило готовности фрагмента

Разделение сигналов:

**Наблюдаемые (детерминированные):** raw_answer; claims_covered/missed; target_phrases_used; copy_similarity; blocking_error_count; число сессий по материалу.

**Субъективные (LLM), помечены и ни на что не влияют:** качество структуры ответа, комментарий коуча.

**Честное ограничение:** «объяснил без чтения» в текстовом режиме ненаблюдаемо. Продукт не заявляет этого. Прокси — anti-copy: если ответ пользователя ≥ 0.5 n-gram overlap с выданным пересказом/фрагментом, ставится `self_built_answer=false`, сессия не засчитывается в готовность. Это ловит копирование текста модели (риск 3), но не чтение с листа вслух — и дизайн это прямо фиксирует, не обещая ложную измеримость речи.

**Правило готовности (проверяемое, а не лозунг):**

```text
fragment.status = ready  ⟺
  для каждого claim_id фрагмента существует session_evidence, где
    claim_id ∈ claims_covered
    и self_built_answer = true
    и blocking_error_count ≤ 2
  и фрагмент прошёл level-чек (п.9)
иначе: rehearsed (частичное покрытие) | draft (ни одной сессии)
```

Правило вычисляется сервером при записи evidence; snapshot отдаёт статус + machine-readable `reason` («claim-3 not yet defended»). Отсутствие уверенного результата порождает следующую миссию, а не публикацию.

## 11. План проверок

**Модульные (`tests/test_source_material_service.py` и рядом):**
- валидатор цитат: сфабрикованная цитата отбрасывается; verbatim принимается; нормализация пробелов;
- лимит длины: источник сверх лимита отклоняется с просьбой выбрать раздел (не молчаливая обрезка);
- инъекция: fixture-статья с «Ignore previous instructions…» — текст инъекции не может стать claim (нет verbatim-опоры на содержательный источник → отбрасывается валидатором либо не проходит quote-чек), пакет валиден;
- anti-copy: скопированный retell → `self_built_answer=false`; свой ответ → true;
- правило готовности: полное покрытие → ready; частичное → rehearsed; копия → не засчитано;
- level-чек: длинные предложения → `needs_simplification`;
- `recommend_next_mission`: активный материал с missed claims → repeat-миссия с объяснимым reason.

**Интеграционные:**
- API round-trip: вставка реального markdown → пакет в roadmap → snapshot показывает материал;
- e2e сессия с `deterministic_routing` fixture: миссия → ходы → evidence с claim-полями;
- replay по `session_id` объясняет статус фрагмента (обязательная часть, по Gate D).

**Продуктовая проверка на первом реальном материале:**
- вставить раздел «Центральный инвариант системы» из `статья.md`;
- founder проходит typed-сессию; оператор сверяет claims_covered с реальностью ответа вручную;
- критерий: replay-бандл объясняет, почему фрагмент готов/не готов, без чтения кода.

## 12. Угрозы и защита по рискам задания

| # | Риск | Защита | Тест |
| --- | --- | --- | --- |
| 1 | Несоответствие источнику | verbatim `source_quote` как обязательная опора каждого утверждения; извлечение LLM, вето — детерминированное | unit: fabricated quote rejected |
| 2 | Разрыв ожиданий (C1 vs A2–B1) | level-чек фрагментов + готовность только через собственную защиту | unit: level check; продуктовая проверка |
| 3 | Подмена тренировки | anti-copy n-gram, копия не засчитывается в готовность | unit: copied retell |
| 4 | Инъекции в источнике | источник в delimited-блоке как данные; структурный JSON-выход; quote-валидация отсекает внесённый контент | unit: injection fixture |
| 5 | Список слов вместо навыка | `target_phrases_used` — только фактическое употребление в user-turns | unit: phrase matching |
| 6 | Разрастание продукта | материал неизменяем; нет редактора/публикации; всё внутри Mission→Evidence→Next Mission | code review + границы v1 (п.14) |
| 7 | Потеря происхождения | `content_sha256` + `material_id` в каждом evidence и фрагменте | integration: evidence carries hash |
| 8 | Слишком длинный материал | жёсткий лимит (предложение: 12 000 символов); сверх лимита — явный выбор раздела, отказ вместо тихой обрезки | unit: over-limit rejected |

Конфиденциальность/авторство: только собственные тексты; `authorship_confirmed` обязателен в API; чужие URL и скачивание отсутствуют по построению. Источник хранится в том же Postgres, что и остальной пользовательский контент, — новых поверхностей утечки нет.

## 13. Этапы реализации

| Этап | Содержание | Размер | Стоп-точка / откат |
| --- | --- | --- | --- |
| 0 | Ручная проверка: founder проходит существующий `technical_project_walkthrough` typed-сессией по grounded-judge-gate со статьёй под рукой; заодно закрывает давно ожидаемый founder dogfood run | 0 LOC | если тренировка не даёт ценности — гипотезу закрыть, ничего не строить |
| 1 | Приём источника + пакет: endpoint, `source_material_service`, валидаторы, тесты | ~350–400 строк | самостоятельно полезен (пакет виден в snapshot); откат — игнорировать ключ roadmap |
| 2 | Миссия: task_type, промпт-spec, evidence-поля, ветка next mission | ~300 строк | откат — убрать task_type из реестров, evidence-поля безвредны |
| 3 | Готовность фрагментов + snapshot-секция + минимальный frontend (вставка + статусы) | ~250 строк | откат — не рендерить секцию |

Каждый этап — отдельный PR ≤ 400 строк. Данные только в roadmap JSON, миграций нет, откат любого этапа не ломает существующие сессии.

## 14. Жёсткая граница первой версии

Не входит (подтверждение ограничений задания + решения дизайна):
- голос; автопубликация в LinkedIn; полный перевод статьи; URL-скачивание; чужие материалы;
- редактор/переводчик/«раздел статей»; Qdrant/Neo4j; новая система баллов;
- динамические слоты MissionContract из claim map (этап «потом», если статический контракт окажется слепым);
- несколько активных материалов одновременно (v1 — один);
- новая таблица БД для материалов;
- какая-либо оценка произношения или «говорения без чтения» — текстовый режим этого честно не измеряет.

## 15. Открытые вопросы владельцу продукта (только влияющие на архитектуру)

1. **Хранение source_text в roadmap JSONB** (консистентно с `vacancy_text`, ноль миграций) vs отдельная таблица. Рекомендация: roadmap сейчас; таблица — только когда материалов станет много.
2. **Приоритет миссии материала**: пока у активного материала есть непокрытые утверждения, `recommend_next_mission` предлагает его раньше interview-pack трека? Рекомендация: да, но только если материал создан явно пользователем в этом цикле; weakest-area-миссии из интервью-runs сохраняют приоритет.
3. **Anti-copy как честный прокси**: согласны ли, что «объяснил без чтения» в тексте заменяется на «не скопировал текст модели» без претензии на большее? (Если нет — фича должна ждать голосового режима, что противоречит text-first.)
4. **Порог готовности** `blocking_error_count ≤ 2`: границу задаёт владелец; в дизайне это одно число в конфиге правила, не архитектура.

## Приложение: компактный пример данных (grounded-judge-gate, только реальные факты)

```yaml
source_fragment:  # verbatim из статья.md, раздел «Центральный инвариант системы»
  quote: "ответ нельзя принять, пока каноническое значение не прошло детерминированного
    арбитра — сразу или после извлечения моделью"

claim:
  id: claim-invariant
  statement_en_simple: "The system never accepts an answer on the LLM's word alone.
    The LLM can only extract a value. Deterministic code checks that value again."
  key_terms: ["deterministic check", "extracted value", "manual review"]

simple_english_version: "My checker has three outcomes, not two. Clear numbers are
  accepted or rejected by code. Unclear text goes to the LLM, but the LLM only
  extracts a value. The same code checks it again. Unresolved cases go to a human."

interviewer_question:
  audience: technical
  question_en: "What happens when the LLM says two answers are equivalent,
    but the extracted value does not match the canonical one?"
  claim_ids: [claim-invariant]

raw_user_answer: "The system not accept it. The extracted value go to the authority
  check again. If it not match the canonical answer, the case go to manual review
  with reason ungrounded rescue."

observed_result:
  claims_covered: [claim-invariant]
  target_phrases_used: ["manual review", "extracted value"]
  copy_similarity: 0.14
  self_built_answer: true
  blocking_error_count: 2   # пропуск вспомогательных глаголов — recast дан, интервью не ломает

next_mission:
  task_type: source_material_walkthrough
  reason: "claim about kappa contract mismatch is still missed"
  repeat_vs_advance: repeat
```
