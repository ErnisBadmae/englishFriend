"""ML technical interview question pack for the `ml_technical` track.

This module is intentionally separate from `app/data/interview_questions.py`.
The existing question bank models a different shape (behavioral/technical
`prompt` + `follow_up_prompts`, difficulty-bucketed selection). ML technical
questions need an authoritative rubric, a hidden reference explanation, a
topic taxonomy, and repetition-aware selection — reusing the existing shape
would force a fit that does not honestly represent either track.

The question pack below is the checked-in authority for rubric content. The
runtime reviewer (see `app/services/ml_technical_reviewer.py`) must never
invent rubric points — it only grades against what is defined here.

Provenance: all 15 questions are drawn from the founder's own local prep
notes, not from any Telegram channel or URL:
- career/DL_INTERVIEW_PREP_PLAN.md ("Первые 15 вопросов" section,
  dated 2026-07-17) — the source list and order for all 15 questions.
- telegram-digest/data/dl_questions_sonnet_audit.md — a manual audit report
  (no URLs, no channel metadata) used only to cross-check technical framing
  (e.g. that BatchNorm's gamma/beta, Flash Attention's memory-vs-math split,
  and KV-cache's K/V-only scope are the commonly asked angles).
`provenance_id` below cites the local plan file and item index only.
"""

from __future__ import annotations

from typing import Any

RUBRIC_VERSION = "ml-technical-v1"
PROVENANCE_SOURCE = "career/DL_INTERVIEW_PREP_PLAN.md#2026-07-17-top-15"


ML_TECHNICAL_TOPICS: list[dict[str, Any]] = [
    {
        "id": "ml_fundamentals",
        "title_ru": "Основы ML/DL",
        "description_ru": "Градиенты, backprop, оптимизация — фундамент перед архитектурами.",
    },
    {
        "id": "dl_training",
        "title_ru": "Обучение нейросетей",
        "description_ru": "Learning rate, нормализация, регуляризация, оптимизаторы.",
    },
    {
        "id": "transformers_llm",
        "title_ru": "Трансформеры и LLM",
        "description_ru": "Attention, positional encoding, архитектура трансформера целиком.",
    },
    {
        "id": "finetuning_peft",
        "title_ru": "Fine-tuning и PEFT",
        "description_ru": "LoRA, QLoRA и практика дообучения больших моделей.",
    },
    {
        "id": "inference_mlops",
        "title_ru": "Inference и MLOps",
        "description_ru": "Квантизация, KV-cache, память и latency в проде.",
    },
    {
        "id": "rag_agents_evaluation",
        "title_ru": "RAG, агенты, оценка",
        "description_ru": "Retrieval, инструменты и оценка LLM-систем.",
    },
    {
        "id": "recsys_ranking",
        "title_ru": "Рекомендательные системы и ранжирование",
        "description_ru": "Кандидатогенерация, ранжирование, метрики recsys.",
    },
]

_TOPIC_IDS = {topic["id"] for topic in ML_TECHNICAL_TOPICS}


def _q(
    idx: int,
    *,
    topic_id: str,
    question_ru: str,
    difficulty: str,
    tags: list[str],
    rubric_points: list[tuple[str, str]],
    reference_explanation_ru: str,
    follow_ups: list[str],
) -> dict[str, Any]:
    assert topic_id in _TOPIC_IDS, f"unknown topic_id {topic_id}"
    assert difficulty in ("easy", "medium", "hard")
    assert len(follow_ups) == 2, "exactly two interviewer follow-ups are required"
    assert len(rubric_points) >= 3, "rubric needs at least three required technical points"
    return {
        "id": f"mltech_{idx:03d}",
        "track_id": "ml_technical",
        "topic_id": topic_id,
        "question_ru": question_ru,
        "difficulty": difficulty,
        "tags": tags,
        "rubric_points": [{"id": point_id, "point_ru": point_ru} for point_id, point_ru in rubric_points],
        "reference_explanation_ru": reference_explanation_ru,
        "follow_ups": follow_ups,
        "rubric_version": RUBRIC_VERSION,
        "provenance_id": f"{PROVENANCE_SOURCE}-q{idx}",
    }


ML_TECHNICAL_QUESTIONS: list[dict[str, Any]] = [
    _q(
        1,
        topic_id="dl_training",
        question_ru="Как выбирать learning rate и по каким признакам понимать, что он подобран неверно?",
        difficulty="easy",
        tags=["learning_rate", "optimization", "training_diagnostics"],
        rubric_points=[
            ("lr_definition", "LR — коэффициент шага обновления весов: w -= lr * grad."),
            ("too_high", "Слишком большой LR: loss растёт, скачет или расходится (divergence)."),
            ("too_low", "Слишком маленький LR: loss убывает очень медленно, обучение почти не сходится за разумное время."),
            ("selection_method", "LR подбирают через LR range test, warmup и scheduler (cosine/step decay), наблюдая за кривой loss."),
        ],
        reference_explanation_ru=(
            "Learning rate масштабирует шаг градиентного спуска. Слишком большой LR даёт "
            "нестабильный или расходящийся loss; слишком маленький — крайне медленную сходимость "
            "или застревание. На практике LR подбирают через LR range test (постепенно повышают LR "
            "и смотрят, где loss начинает расти) и используют warmup плюс scheduler."
        ),
        follow_ups=[
            "Зачем нужен warmup в начале обучения трансформеров?",
            "Как именно проводится LR range test и что на нём ищут?",
        ],
    ),
    _q(
        2,
        topic_id="dl_training",
        question_ru="Что делают параметры gamma и beta в BatchNorm? Чем BatchNorm отличается на train и на inference?",
        difficulty="medium",
        tags=["batchnorm", "normalization", "train_vs_inference"],
        rubric_points=[
            ("normalize_step", "BatchNorm сначала нормализует активации по батчу: вычитает батчевое среднее, делит на батчевое std."),
            ("gamma_beta_role", "gamma и beta — обучаемые параметры, которые масштабируют и сдвигают нормализованный выход, чтобы не терять выразительность сети."),
            ("train_stats", "На train статистики (mean/var) считаются по текущему батчу и накапливается running-статистика (EMA)."),
            ("inference_stats", "На inference используется зафиксированная running-статистика, а не статистика текущего батча, иначе результат зависел бы от размера батча."),
        ],
        reference_explanation_ru=(
            "BatchNorm нормализует активации слоя по статистикам батча (среднее и дисперсия), "
            "а затем gamma и beta — обучаемые параметры — восстанавливают нужный масштаб и сдвиг, "
            "чтобы нормализация не ограничивала выразительность сети. На train статистики берутся "
            "из текущего батча и накапливаются как running-среднее; на inference используется эта "
            "зафиксированная running-статистика, чтобы выход не зависел от батча на инференсе."
        ),
        follow_ups=[
            "Почему BatchNorm плохо работает с очень маленьким batch size?",
            "Чем LayerNorm отличается от BatchNorm по оси нормализации?",
        ],
    ),
    _q(
        3,
        topic_id="inference_mlops",
        question_ru="Что такое квантизация нейросети, какие виды бывают и что теряется при переходе FP16 → INT8/INT4?",
        difficulty="medium",
        tags=["quantization", "inference", "fp16", "int8", "int4"],
        rubric_points=[
            ("definition", "Квантизация — представление весов/активаций в формате с меньшей битностью (например INT8/INT4 вместо FP16/FP32) для экономии памяти и ускорения inference."),
            ("types", "Есть post-training квантизация и quantization-aware training; есть weight-only и weight+activation квантизация."),
            ("precision_loss", "Снижение битности снижает точность представления чисел, что может ухудшать качество модели, особенно на выбросах и чувствительных слоях."),
            ("mitigation", "Потери частично компенсируют калибровкой, группировкой по блокам (group-wise quantization) или отдельными форматами для outlier-весов."),
        ],
        reference_explanation_ru=(
            "Квантизация переводит веса и/или активации в формат с меньшей битностью — например, "
            "INT8 или INT4 вместо FP16 — чтобы уменьшить объём памяти и ускорить вычисления. Бывает "
            "post-training квантизация (без дообучения) и quantization-aware training (с адаптацией "
            "весов под квантизацию). При переходе к INT8/INT4 теряется точность представления чисел, "
            "что может ухудшить качество, особенно из-за весовых выбросов; это частично компенсируют "
            "калибровкой и группировкой по блокам."
        ),
        follow_ups=[
            "Что такое group-wise квантизация и зачем она нужна?",
            "Почему активации обычно квантуют осторожнее, чем веса?",
        ],
    ),
    _q(
        4,
        topic_id="transformers_llm",
        question_ru="Зачем нужен positional encoding в трансформере и какие ограничения он создаёт?",
        difficulty="medium",
        tags=["positional_encoding", "transformer", "attention"],
        rubric_points=[
            ("why_needed", "Self-attention сам по себе не учитывает порядок токенов (перестановочно-инвариантен), поэтому позицию нужно добавлять явно."),
            ("mechanism", "Positional encoding добавляет к эмбеддингу токена информацию о его позиции (синусоидальная, обучаемая или относительная, например RoPE)."),
            ("limitation_length", "Фиксированный positional encoding ограничивает или ухудшает экстраполяцию на последовательности длиннее, чем видела модель при обучении."),
            ("limitation_choice", "Выбор схемы (абсолютная/относительная) — компромисс между простотой и способностью обобщаться на разные длины контекста."),
        ],
        reference_explanation_ru=(
            "Self-attention не знает порядок токенов — без дополнительной информации перестановка "
            "входа не меняет результат. Positional encoding добавляет позиционную информацию к "
            "эмбеддингам (синусоидальный, обучаемый или относительный вариант вроде RoPE). Ограничение "
            "в том, что схема, зафиксированная под определённую длину контекста, может плохо "
            "экстраполироваться на более длинные последовательности."
        ),
        follow_ups=[
            "Чем RoPE отличается от классического синусоидального positional encoding?",
            "Что происходит с качеством модели за пределами длины контекста, на которой она обучалась?",
        ],
    ),
    _q(
        5,
        topic_id="transformers_llm",
        question_ru="Что меняет Flash Attention: математический результат attention или способ его вычисления и работу с памятью?",
        difficulty="hard",
        tags=["flash_attention", "memory", "kernel_fusion"],
        rubric_points=[
            ("math_unchanged", "Flash Attention вычисляет математически тот же результат attention (softmax(QK^T/sqrt(d))V), не меняя формулу."),
            ("how_it_changes", "Меняется способ вычисления: блочное (tiled) вычисление и fused-кернел вместо материализации полной матрицы attention."),
            ("memory_benefit", "За счёт этого не хранится полная N×N матрица attention в памяти — память растёт линейно, а не квадратично от длины последовательности."),
            ("speed_benefit", "Ускорение достигается за счёт меньшего числа обращений к медленной HBM-памяти GPU (IO-aware алгоритм), а не за счёт меньшего числа арифметических операций."),
        ],
        reference_explanation_ru=(
            "Flash Attention не меняет математику attention — результат тот же softmax(QK^T/√d)V. "
            "Меняется способ вычисления: блочный (tiled) fused-кернел, который не материализует "
            "полную N×N матрицу attention в памяти GPU. Это даёт линейный, а не квадратичный расход "
            "памяти по длине последовательности и ускорение за счёт меньшего числа обращений к "
            "медленной HBM-памяти, а не за счёт уменьшения числа арифметических операций."
        ),
        follow_ups=[
            "Почему обращения к HBM-памяти являются узким местом, а не сами арифметические операции?",
            "Как Flash Attention влияет на возможность работать с более длинным контекстом?",
        ],
    ),
    _q(
        6,
        topic_id="transformers_llm",
        question_ru="Чем self-attention отличается от attention в классическом encoder-decoder (seq2seq) механизме?",
        difficulty="medium",
        tags=["self_attention", "seq2seq", "encoder_decoder"],
        rubric_points=[
            ("self_attention_scope", "Self-attention считает Q, K, V из одной и той же последовательности — токены смотрят друг на друга внутри одного набора."),
            ("classic_attention_scope", "Классический seq2seq attention (например Bahdanau/Luong) считает attention между декодером (Q) и энкодером (K, V) — это cross-attention между двумя разными последовательностями."),
            ("purpose_difference", "Self-attention строит контекстуализированное представление внутри последовательности; классический attention передаёт информацию из энкодера в декодер на каждом шаге генерации."),
            ("architecture_context", "В трансформере оба вида присутствуют: self-attention в энкодере и декодере плюс cross-attention между ними."),
        ],
        reference_explanation_ru=(
            "Self-attention вычисляет Q, K и V из одной последовательности — токены обращают "
            "внимание друг на друга внутри одного набора данных. Классический attention в seq2seq "
            "(например, Bahdanau или Luong) — это cross-attention между декодером (запрос) и "
            "энкодером (ключи и значения), передающий информацию из входной последовательности на "
            "каждом шаге генерации выхода. В трансформере есть оба механизма: self-attention внутри "
            "энкодера и декодера, и cross-attention между ними."
        ),
        follow_ups=[
            "Где именно в декодере трансформера используется cross-attention к энкодеру?",
            "Почему self-attention даёт более параллелизуемое вычисление, чем рекуррентный attention в RNN?",
        ],
    ),
    _q(
        7,
        topic_id="finetuning_peft",
        question_ru="Как устроена LoRA: матрицы A и B, ранг, инициализация и применение на inference?",
        difficulty="hard",
        tags=["lora", "peft", "finetuning"],
        rubric_points=[
            ("decomposition", "LoRA замораживает исходную матрицу весов W и добавляет к ней низкоранговое обновление: W' = W + B·A, где A и B — маленькие матрицы ранга r << d."),
            ("rank_role", "Ранг r — гиперпараметр, задающий размер обучаемых матриц и компромисс между качеством адаптации и числом обучаемых параметров."),
            ("initialization", "Обычно A инициализируется случайно (например, гауссовым шумом), а B — нулями, так что в начале обучения B·A = 0 и модель стартует как исходная предобученная."),
            ("inference_application", "На inference B·A можно либо оставить отдельным адаптером (легко переключать), либо слить (merge) в исходные веса W, чтобы не терять скорость по сравнению с базовой моделью."),
        ],
        reference_explanation_ru=(
            "LoRA замораживает исходные веса W и добавляет к ним низкоранговое обновление B·A, где "
            "A и B — матрицы малого ранга r, а обучаются только они. Ранг r задаёт компромисс между "
            "выразительностью адаптации и числом обучаемых параметров. Инициализация: A — случайная, "
            "B — нулевая, поэтому в начале обучения добавка равна нулю и модель совпадает с базовой. "
            "На inference адаптер B·A можно применять отдельно (для быстрого переключения между "
            "задачами) или слить в исходные веса, чтобы не терять скорость инференса."
        ),
        follow_ups=[
            "Почему инициализация B нулями важна для стабильности старта обучения?",
            "К каким весам трансформера чаще всего применяют LoRA (например, к каким проекциям attention)?",
        ],
    ),
    _q(
        8,
        topic_id="transformers_llm",
        question_ru="Зачем нужны Multi-Head Attention и Multi-Query Attention, и какие у них компромиссы?",
        difficulty="hard",
        tags=["multi_head_attention", "multi_query_attention", "kv_cache"],
        rubric_points=[
            ("multi_head_purpose", "Multi-Head Attention считает несколько параллельных attention-голов с разными проекциями Q/K/V, позволяя модели учитывать разные типы зависимостей одновременно."),
            ("multi_head_cost", "Каждая голова в MHA хранит собственные K и V, что увеличивает объём KV-cache пропорционально числу голов."),
            ("mqa_idea", "Multi-Query Attention использует общие K и V на все головы (разные только Q), что резко уменьшает размер KV-cache и ускоряет инференс."),
            ("tradeoff", "Компромисс MQA — экономия памяти и latency ценой потенциально меньшей выразительности/качества по сравнению с полным MHA; GQA (grouped-query attention) — промежуточный вариант."),
        ],
        reference_explanation_ru=(
            "Multi-Head Attention считает несколько attention-голов параллельно с разными "
            "проекциями Q/K/V, что позволяет модели одновременно учитывать разные виды зависимостей "
            "между токенами. Цена — каждая голова хранит свои K и V, и KV-cache растёт пропорционально "
            "числу голов. Multi-Query Attention делает K и V общими для всех голов (различаются "
            "только Q), сильно уменьшая KV-cache и ускоряя инференс, но потенциально немного теряя в "
            "качестве по сравнению с полным MHA; grouped-query attention — компромисс между этими "
            "двумя крайностями."
        ),
        follow_ups=[
            "Как GQA (grouped-query attention) располагается между MHA и MQA?",
            "Почему уменьшение KV-cache особенно важно при батчевом инференсе с длинным контекстом?",
        ],
    ),
    _q(
        9,
        topic_id="dl_training",
        question_ru="Какие виды регуляризации нейросетей есть и какой конкретный дефект обучения лечит каждый метод?",
        difficulty="easy",
        tags=["regularization", "overfitting", "generalization"],
        rubric_points=[
            ("l2_weight_decay", "L2-регуляризация (weight decay) штрафует большие веса, борется с переобучением, сглаживая функцию модели."),
            ("dropout", "Dropout случайно зануляет часть активаций на train, борется с ко-адаптацией нейронов и переобучением."),
            ("early_stopping", "Early stopping останавливает обучение при росте ошибки на валидации, борется с переобучением на поздних эпохах."),
            ("data_augmentation", "Аугментация данных увеличивает эффективное разнообразие обучающей выборки, борется с переобучением при ограниченных данных."),
        ],
        reference_explanation_ru=(
            "Основные виды регуляризации: L2/weight decay — штрафует большие веса и сглаживает "
            "функцию модели против переобучения; dropout — случайно зануляет активации на train, "
            "борясь с ко-адаптацией нейронов; early stopping — останавливает обучение при росте "
            "ошибки на валидации; аугментация данных — расширяет эффективное разнообразие обучающей "
            "выборки. Каждый метод атакует переобучение с разной стороны — веса, совместную адаптацию "
            "нейронов, момент остановки или сами данные."
        ),
        follow_ups=[
            "Почему dropout выключается на инференсе и как компенсируется масштаб активаций?",
            "Чем L1-регуляризация отличается от L2 по влиянию на веса?",
        ],
    ),
    _q(
        10,
        topic_id="dl_training",
        question_ru="Как dropout работает во время обучения и почему он выключается на инференсе?",
        difficulty="easy",
        tags=["dropout", "train_vs_inference", "regularization"],
        rubric_points=[
            ("train_mechanism", "На train dropout случайно зануляет часть нейронов/активаций с вероятностью p на каждом forward-проходе."),
            ("purpose", "Это мешает нейронам чрезмерно полагаться друг на друга (ко-адаптации) и работает как регуляризация против переобучения."),
            ("inference_off", "На inference dropout выключают, чтобы предсказание было детерминированным и использовало всю сеть целиком."),
            ("scaling", "Чтобы ожидаемая величина активаций совпадала между train и inference, применяют масштабирование (inverted dropout: деление на (1-p) на train, либо умножение на (1-p) на inference)."),
        ],
        reference_explanation_ru=(
            "На train dropout случайно зануляет часть активаций с вероятностью p на каждом "
            "forward-проходе, что мешает нейронам чрезмерно полагаться друг на друга и работает как "
            "регуляризация. На inference dropout выключают, чтобы предсказание было детерминированным "
            "и использовало всю сеть. Чтобы масштаб активаций совпадал между train и inference, "
            "используют inverted dropout — масштабирование оставшихся активаций на train на 1/(1-p)."
        ),
        follow_ups=[
            "Что такое inverted dropout и зачем нужно масштабирование на train?",
            "Как dropout соотносится с DropPath/Stochastic Depth в глубоких сетях?",
        ],
    ),
    _q(
        11,
        topic_id="transformers_llm",
        question_ru="Как устроен трансформер целиком: encoder/decoder, Q/K/V, attention, FFN, residual connections, normalization?",
        difficulty="medium",
        tags=["transformer_architecture", "attention", "ffn", "residual", "normalization"],
        rubric_points=[
            ("qkv", "Q, K, V — проекции входных эмбеддингов; attention считает веса как softmax(QK^T/√d) и взвешивает V."),
            ("encoder_decoder_blocks", "Энкодер строит представление входа через self-attention + FFN; декодер дополнительно использует masked self-attention (авторегрессия) и cross-attention к энкодеру."),
            ("ffn", "После attention в каждом блоке стоит position-wise feed-forward сеть (обычно с расширением размерности и нелинейностью), применяемая к каждому токену независимо."),
            ("residual_and_norm", "Residual connections (skip-соединения) вокруг attention и FFN плюс normalization (LayerNorm, pre-norm или post-norm) стабилизируют обучение глубоких стеков блоков."),
        ],
        reference_explanation_ru=(
            "Трансформер строится из блоков, каждый из которых содержит self-attention и "
            "position-wise feed-forward сеть (FFN), обёрнутые в residual connections и normalization "
            "(LayerNorm). Attention считает Q, K, V из входа и взвешивает V весами softmax(QK^T/√d). "
            "Энкодер применяет self-attention и FFN к входу; декодер дополнительно использует masked "
            "self-attention (чтобы не заглядывать вперёд при генерации) и cross-attention к выходу "
            "энкодера. Residual connections и normalization нужны, чтобы градиенты стабильно "
            "проходили через глубокий стек блоков."
        ),
        follow_ups=[
            "В чём разница между pre-norm и post-norm расположением LayerNorm в блоке трансформера?",
            "Зачем в decoder self-attention нужна маска (causal mask)?",
        ],
    ),
    _q(
        12,
        topic_id="dl_training",
        question_ru="Чем AdamW отличается от Adam, а Momentum — от обычного SGD?",
        difficulty="medium",
        tags=["optimizers", "adam", "adamw", "sgd", "momentum"],
        rubric_points=[
            ("adam_mechanism", "Adam хранит оценки первого и второго моментов градиента (аналог momentum + адаптивный per-parameter learning rate) и использует их для обновления весов."),
            ("adam_weight_decay_issue", "В классическом Adam weight decay реализован как L2-штраф внутри градиента, из-за чего он смешивается с адаптивным масштабированием и работает не совсем как ожидаемая регуляризация."),
            ("adamw_fix", "AdamW отделяет weight decay от градиентного шага (decoupled weight decay) — вычитает weight decay из весов напрямую, а не через градиент, что даёт более предсказуемую регуляризацию."),
            ("momentum_vs_sgd", "Momentum добавляет к обычному SGD накопление скользящего среднего прошлых градиентов (velocity), что ускоряет движение в устойчивом направлении и сглаживает колебания по сравнению с чистым SGD."),
        ],
        reference_explanation_ru=(
            "Adam хранит оценки первого и второго моментов градиента и адаптирует learning rate "
            "по каждому параметру. В классическом Adam weight decay реализован как L2-штраф внутри "
            "градиента и смешивается с адаптивным масштабированием, что делает регуляризацию менее "
            "предсказуемой. AdamW отделяет weight decay от градиентного шага (decoupled weight decay), "
            "вычитая его из весов напрямую. Momentum добавляет к обычному SGD накопление скользящего "
            "среднего прошлых градиентов (velocity), что ускоряет движение в устойчивом направлении и "
            "сглаживает колебания по сравнению с шагом чистого SGD, который использует только текущий "
            "градиент."
        ),
        follow_ups=[
            "Почему decoupled weight decay в AdamW считается более честной регуляризацией?",
            "Что произойдёт с обучением, если momentum слишком большой?",
        ],
    ),
    _q(
        13,
        topic_id="ml_fundamentals",
        question_ru="Почему возникают vanishing и exploding gradients, как их диагностировать и как исправлять?",
        difficulty="medium",
        tags=["vanishing_gradients", "exploding_gradients", "backprop", "training_diagnostics"],
        rubric_points=[
            ("cause", "При backprop градиент — произведение множества производных по слоям; если эти множители систематически <1 (или >1), произведение экспоненциально затухает (или взрывается) с глубиной сети."),
            ("vanishing_symptoms", "Признаки vanishing gradients: ранние слои почти не обучаются, loss стагнирует, веса первых слоёв почти не меняются."),
            ("exploding_symptoms", "Признаки exploding gradients: loss резко скачет или становится NaN/Inf, норма градиентов аномально большая."),
            ("fixes", "Исправления: подходящая инициализация весов, нормализация (BatchNorm/LayerNorm), residual connections, gradient clipping (для взрыва), смена функции активации (например ReLU вместо sigmoid/tanh)."),
        ],
        reference_explanation_ru=(
            "При обратном распространении градиент по ранним слоям — произведение множества "
            "локальных производных. Если эти множители систематически меньше единицы, произведение "
            "экспоненциально затухает с глубиной (vanishing gradients); если больше единицы — "
            "экспоненциально растёт (exploding gradients). Диагностика: vanishing — ранние слои почти "
            "не обучаются, loss стагнирует; exploding — loss скачет или становится NaN, норма "
            "градиента аномально велика. Лечение: подходящая инициализация, нормализация слоёв, "
            "residual connections, gradient clipping (при взрыве) и функции активации без насыщения "
            "(например ReLU вместо sigmoid/tanh)."
        ),
        follow_ups=[
            "Как residual connections конкретно помогают против vanishing gradients?",
            "Что такое gradient clipping и как выбирают порог для него?",
        ],
    ),
    _q(
        14,
        topic_id="inference_mlops",
        question_ru="Что именно хранит KV-cache, почему кэшируют K и V, а не Q, и как это влияет на память и latency?",
        difficulty="hard",
        tags=["kv_cache", "inference", "latency", "memory"],
        rubric_points=[
            ("what_is_cached", "KV-cache хранит вычисленные ключи (K) и значения (V) для всех уже сгенерированных токенов, чтобы не пересчитывать их заново на каждом новом шаге генерации."),
            ("why_not_q", "Q нужен только для текущего шага (запрос от нового токена к прошлому контексту), а не переиспользуется для будущих шагов, поэтому кэшировать его не нужно; K и V от прошлых токенов остаются неизменными и переиспользуются на каждом новом шаге."),
            ("memory_impact", "Размер KV-cache растёт линейно с длиной последовательности и числом слоёв/голов, и может стать доминирующим потребителем GPU-памяти при длинном контексте и большом батче."),
            ("latency_impact", "Без KV-cache пришлось бы пересчитывать attention по всей истории на каждом шаге генерации (квадратичная стоимость); с кэшем каждый новый токен считается за счёт одного дополнительного шага, что резко снижает latency автогрегрессивной генерации."),
        ],
        reference_explanation_ru=(
            "KV-cache хранит вычисленные ключи (K) и значения (V) для уже сгенерированных токенов, "
            "чтобы не пересчитывать attention по всей истории заново на каждом шаге. Q кэшировать не "
            "нужно — он представляет запрос текущего шага и не переиспользуется в будущем, тогда как "
            "K и V прошлых токенов не меняются и годятся для всех последующих шагов. Размер KV-cache "
            "растёт линейно с длиной последовательности, числом слоёв и голов и может стать основным "
            "потребителем GPU-памяти при длинном контексте. Без кэша генерация каждого нового токена "
            "требовала бы пересчёта attention по всей истории, что резко увеличивает latency "
            "автогрегрессивной генерации."
        ),
        follow_ups=[
            "Как Multi-Query или Grouped-Query Attention уменьшают размер KV-cache?",
            "Что такое continuous batching и как он взаимодействует с KV-cache в системах вроде vLLM?",
        ],
    ),
    _q(
        15,
        topic_id="finetuning_peft",
        question_ru="Чем QLoRA отличается от LoRA и что именно в QLoRA квантуется?",
        difficulty="hard",
        tags=["qlora", "lora", "quantization", "peft"],
        rubric_points=[
            ("base_model_quantized", "В QLoRA замороженная базовая модель хранится в низкобитном квантизованном формате (обычно 4-bit, NormalFloat4), а не в FP16/BF16 как в обычной LoRA."),
            ("adapters_stay_precise", "Обучаемые LoRA-адаптеры (матрицы A и B) остаются в более высокой точности (например BF16) и обучаются поверх квантизованной базовой модели."),
            ("memory_benefit", "Основной выигрыш QLoRA — резкое снижение памяти для хранения замороженных весов, что позволяет дообучать модели существенно большего размера на одной GPU."),
            ("dequantization_at_compute", "Во время forward/backward квантизованные веса на лету деквантизуются в вычислительный формат более высокой точности для матричного умножения, а хранятся при этом в низкобитном виде."),
        ],
        reference_explanation_ru=(
            "В обычной LoRA замороженная базовая модель хранится в исходной точности (например "
            "FP16/BF16), и обучаются только маленькие матрицы-адаптеры A и B. QLoRA дополнительно "
            "квантует саму замороженную базовую модель в низкобитный формат (обычно 4-bit "
            "NormalFloat4), тогда как LoRA-адаптеры остаются в более высокой точности и обучаются "
            "поверх квантизованных весов. Во время вычислений квантизованные веса на лету "
            "деквантизуются для матричного умножения, а хранятся в памяти в низкобитном виде. "
            "Основной эффект — резкое снижение требований к памяти, что позволяет дообучать намного "
            "более крупные модели на одной GPU."
        ),
        follow_ups=[
            "Что такое NormalFloat4 и почему он подходит для весов с нормальным распределением?",
            "Почему LoRA-адаптеры в QLoRA не квантуют так же агрессивно, как базовую модель?",
        ],
    ),
]

assert len(ML_TECHNICAL_QUESTIONS) == 15, "the initial ml_technical pack must contain exactly 15 questions"
assert len({q["id"] for q in ML_TECHNICAL_QUESTIONS}) == 15, "question ids must be unique"


_QUESTION_INDEX: dict[str, dict[str, Any]] = {q["id"]: q for q in ML_TECHNICAL_QUESTIONS}
_TOPIC_QUESTION_INDEX: dict[str, list[dict[str, Any]]] = {}
for _question in ML_TECHNICAL_QUESTIONS:
    _TOPIC_QUESTION_INDEX.setdefault(_question["topic_id"], []).append(_question)


def list_ml_technical_topics() -> list[dict[str, Any]]:
    return [dict(topic) for topic in ML_TECHNICAL_TOPICS]


def get_ml_technical_topic(topic_id: str | None) -> dict[str, Any] | None:
    if not topic_id:
        return None
    normalized = topic_id.strip().lower()
    for topic in ML_TECHNICAL_TOPICS:
        if topic["id"] == normalized:
            return dict(topic)
    return None


def list_ml_technical_questions(topic_id: str | None = None) -> list[dict[str, Any]]:
    if topic_id is None:
        return [dict(q) for q in ML_TECHNICAL_QUESTIONS]
    return [dict(q) for q in _TOPIC_QUESTION_INDEX.get(topic_id, [])]


def get_ml_technical_question(question_id: str) -> dict[str, Any] | None:
    question = _QUESTION_INDEX.get(question_id)
    return dict(question) if question else None


def public_question_view(question: dict[str, Any]) -> dict[str, Any]:
    """Question payload safe to show BEFORE submission — no rubric, no reference explanation."""
    return {
        "id": question["id"],
        "topic_id": question["topic_id"],
        "question_ru": question["question_ru"],
        "difficulty": question["difficulty"],
        "tags": list(question.get("tags") or []),
    }
