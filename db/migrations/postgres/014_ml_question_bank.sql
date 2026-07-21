-- Versioned ML interview question bank and exact revision binding.
-- Static Python questions are backfill/reference fixtures only after this cutover.

begin;

create table if not exists ml_question_revisions (
  id uuid primary key default gen_random_uuid(),
  question_key varchar(64) not null,
  revision_no integer not null,
  supersedes_id uuid references ml_question_revisions(id) on delete restrict,
  track_id varchar(40) not null default 'ml_technical',
  status varchar(20) not null default 'draft',
  topic_id varchar(80) not null,
  question_ru text not null,
  difficulty varchar(20) not null,
  tags jsonb not null,
  rubric_points jsonb not null,
  reference_explanation_ru text not null,
  follow_ups jsonb not null,
  rubric_version varchar(120) not null,
  source_kind varchar(40) not null,
  source_label varchar(240) not null,
  source_uri_public text,
  source_fingerprint varchar(64),
  derivation_kind varchar(30) not null,
  publication_scope varchar(40) not null,
  license_note text,
  model_id varchar(160),
  prompt_version varchar(120),
  idempotency_key varchar(240) not null unique,
  content_hash varchar(64) not null,
  created_by varchar(160) not null,
  created_at timestamptz not null,
  approved_by varchar(160),
  approved_at timestamptz,
  retired_by varchar(160),
  retired_at timestamptz,
  retirement_reason text,
  constraint ml_question_revisions_key_revision_key unique (question_key, revision_no),
  constraint ml_question_revisions_revision_check check (revision_no > 0),
  constraint ml_question_revisions_track_check check (track_id = 'ml_technical'),
  constraint ml_question_revisions_status_check check (status in ('draft', 'approved', 'retired')),
  constraint ml_question_revisions_difficulty_check check (difficulty in ('easy', 'medium', 'hard')),
  constraint ml_question_revisions_source_kind_check check (
    source_kind in ('owner_authored', 'public_official', 'public_secondary', 'private_corpus', 'model_authored')
  ),
  constraint ml_question_revisions_derivation_check check (
    derivation_kind in ('original', 'paraphrase', 'synthetic')
  ),
  constraint ml_question_revisions_publication_scope_check check (
    publication_scope in ('internal_only', 'public_paraphrase', 'public_verbatim')
  ),
  constraint ml_question_revisions_tags_array_check check (jsonb_typeof(tags) = 'array'),
  constraint ml_question_revisions_rubric_array_check check (jsonb_typeof(rubric_points) = 'array'),
  constraint ml_question_revisions_followups_array_check check (jsonb_typeof(follow_ups) = 'array'),
  constraint ml_question_revisions_content_hash_check check (content_hash ~ '^[0-9a-f]{64}$'),
  constraint ml_question_revisions_source_fingerprint_check check (
    source_fingerprint is null or source_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  constraint ml_question_revisions_private_source_check check (
    source_kind <> 'private_corpus'
    or (publication_scope = 'internal_only' and source_uri_public is null)
  )
);

create unique index if not exists ml_question_revisions_one_approved_key
  on ml_question_revisions(question_key)
  where status = 'approved';
create unique index if not exists ml_question_revisions_one_draft_key
  on ml_question_revisions(question_key)
  where status = 'draft';
create index if not exists ml_question_revisions_status_topic_idx
  on ml_question_revisions(status, topic_id);

create table if not exists ml_question_reviews (
  id uuid primary key default gen_random_uuid(),
  question_revision_id uuid not null references ml_question_revisions(id) on delete restrict,
  review_kind varchar(30) not null,
  verdict varchar(30) not null,
  findings jsonb not null,
  reviewer_type varchar(30) not null,
  reviewer_id varchar(160) not null,
  model_id varchar(160),
  prompt_version varchar(120),
  input_content_hash varchar(64) not null,
  created_at timestamptz not null,
  constraint ml_question_reviews_kind_check check (review_kind in ('schema', 'technical', 'source_ip')),
  constraint ml_question_reviews_verdict_check check (verdict in ('pass', 'fail', 'needs_changes')),
  constraint ml_question_reviews_reviewer_type_check check (reviewer_type in ('deterministic', 'model', 'human')),
  constraint ml_question_reviews_findings_array_check check (jsonb_typeof(findings) = 'array'),
  constraint ml_question_reviews_content_hash_check check (input_content_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists ml_question_reviews_revision_created_idx
  on ml_question_reviews(question_revision_id, created_at);

-- The generated payload is canonicalized with
-- app.services.ml_question_bank_service.question_content_hash.
create temp table mlq014_fixture(payload jsonb) on commit drop;
insert into mlq014_fixture(payload)
values ($fixture$[{"question_key":"mltech_001","track_id":"ml_technical","topic_id":"dl_training","question_ru":"Как выбирать learning rate и по каким признакам понимать, что он подобран неверно?","difficulty":"easy","tags":["learning_rate","optimization","training_diagnostics"],"rubric_points":[{"id":"lr_definition","point_ru":"LR — коэффициент шага обновления весов: w -= lr * grad."},{"id":"too_high","point_ru":"Слишком большой LR: loss растёт, скачет или расходится (divergence)."},{"id":"too_low","point_ru":"Слишком маленький LR: loss убывает очень медленно, обучение почти не сходится за разумное время."},{"id":"selection_method","point_ru":"LR подбирают через LR range test, warmup и scheduler (cosine/step decay), наблюдая за кривой loss."}],"reference_explanation_ru":"Learning rate масштабирует шаг градиентного спуска. Слишком большой LR даёт нестабильный или расходящийся loss; слишком маленький — крайне медленную сходимость или застревание. На практике LR подбирают через LR range test (постепенно повышают LR и смотрят, где loss начинает расти) и используют warmup плюс scheduler.","follow_ups":["Зачем нужен warmup в начале обучения трансформеров?","Как именно проводится LR range test и что на нём ищут?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"6bd2d9c9-b53f-5613-a9ba-311f55dc3dad","idempotency_key":"backfill:mltech_001:r1","content_hash":"49d2f5bf65d845dc8ea6e3aeb71ce7a5697064d040bdbbc6d9925b7d83e08dcd"},{"question_key":"mltech_002","track_id":"ml_technical","topic_id":"dl_training","question_ru":"Что делают параметры gamma и beta в BatchNorm? Чем BatchNorm отличается на train и на inference?","difficulty":"medium","tags":["batchnorm","normalization","train_vs_inference"],"rubric_points":[{"id":"normalize_step","point_ru":"BatchNorm сначала нормализует активации по батчу: вычитает батчевое среднее, делит на батчевое std."},{"id":"gamma_beta_role","point_ru":"gamma и beta — обучаемые параметры, которые масштабируют и сдвигают нормализованный выход, чтобы не терять выразительность сети."},{"id":"train_stats","point_ru":"На train статистики (mean/var) считаются по текущему батчу и накапливается running-статистика (EMA)."},{"id":"inference_stats","point_ru":"На inference используется зафиксированная running-статистика, а не статистика текущего батча, иначе результат зависел бы от размера батча."}],"reference_explanation_ru":"BatchNorm нормализует активации слоя по статистикам батча (среднее и дисперсия), а затем gamma и beta — обучаемые параметры — восстанавливают нужный масштаб и сдвиг, чтобы нормализация не ограничивала выразительность сети. На train статистики берутся из текущего батча и накапливаются как running-среднее; на inference используется эта зафиксированная running-статистика, чтобы выход не зависел от батча на инференсе.","follow_ups":["Почему BatchNorm плохо работает с очень маленьким batch size?","Чем LayerNorm отличается от BatchNorm по оси нормализации?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"ad9c5d7e-7940-5b44-ae74-4f6fa08c29c1","idempotency_key":"backfill:mltech_002:r1","content_hash":"8543f0d11f30006f8a6e245d0598aa1bbd2eb12ded5663fa665fe8030401a63a"},{"question_key":"mltech_003","track_id":"ml_technical","topic_id":"inference_mlops","question_ru":"Что такое квантизация нейросети, какие виды бывают и что теряется при переходе FP16 → INT8/INT4?","difficulty":"medium","tags":["quantization","inference","fp16","int8","int4"],"rubric_points":[{"id":"definition","point_ru":"Квантизация — представление весов/активаций в формате с меньшей битностью (например INT8/INT4 вместо FP16/FP32) для экономии памяти и ускорения inference."},{"id":"types","point_ru":"Есть post-training квантизация и quantization-aware training; есть weight-only и weight+activation квантизация."},{"id":"precision_loss","point_ru":"Снижение битности снижает точность представления чисел, что может ухудшать качество модели, особенно на выбросах и чувствительных слоях."},{"id":"mitigation","point_ru":"Потери частично компенсируют калибровкой, группировкой по блокам (group-wise quantization) или отдельными форматами для outlier-весов."}],"reference_explanation_ru":"Квантизация переводит веса и/или активации в формат с меньшей битностью — например, INT8 или INT4 вместо FP16 — чтобы уменьшить объём памяти и ускорить вычисления. Бывает post-training квантизация (без дообучения) и quantization-aware training (с адаптацией весов под квантизацию). При переходе к INT8/INT4 теряется точность представления чисел, что может ухудшить качество, особенно из-за весовых выбросов; это частично компенсируют калибровкой и группировкой по блокам.","follow_ups":["Что такое group-wise квантизация и зачем она нужна?","Почему активации обычно квантуют осторожнее, чем веса?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"9233e666-9d9b-518f-ae95-616d80283db0","idempotency_key":"backfill:mltech_003:r1","content_hash":"92b5175519e1cd4052c8f60518351d300dd04b669921c76b61fcb7ac54738dc8"},{"question_key":"mltech_004","track_id":"ml_technical","topic_id":"transformers_llm","question_ru":"Зачем нужен positional encoding в трансформере и какие ограничения он создаёт?","difficulty":"medium","tags":["positional_encoding","transformer","attention"],"rubric_points":[{"id":"why_needed","point_ru":"Self-attention сам по себе не учитывает порядок токенов (перестановочно-инвариантен), поэтому позицию нужно добавлять явно."},{"id":"mechanism","point_ru":"Positional encoding добавляет к эмбеддингу токена информацию о его позиции (синусоидальная, обучаемая или относительная, например RoPE)."},{"id":"limitation_length","point_ru":"Фиксированный positional encoding ограничивает или ухудшает экстраполяцию на последовательности длиннее, чем видела модель при обучении."},{"id":"limitation_choice","point_ru":"Выбор схемы (абсолютная/относительная) — компромисс между простотой и способностью обобщаться на разные длины контекста."}],"reference_explanation_ru":"Self-attention не знает порядок токенов — без дополнительной информации перестановка входа не меняет результат. Positional encoding добавляет позиционную информацию к эмбеддингам (синусоидальный, обучаемый или относительный вариант вроде RoPE). Ограничение в том, что схема, зафиксированная под определённую длину контекста, может плохо экстраполироваться на более длинные последовательности.","follow_ups":["Чем RoPE отличается от классического синусоидального positional encoding?","Что происходит с качеством модели за пределами длины контекста, на которой она обучалась?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"4de29da6-1a7e-5562-b053-cdc9d3c965d3","idempotency_key":"backfill:mltech_004:r1","content_hash":"69306fd2ff152858e5260ecae1d038938922f9821e7f668f80477de3c408c3c3"},{"question_key":"mltech_005","track_id":"ml_technical","topic_id":"transformers_llm","question_ru":"Что меняет Flash Attention: математический результат attention или способ его вычисления и работу с памятью?","difficulty":"hard","tags":["flash_attention","memory","kernel_fusion"],"rubric_points":[{"id":"math_unchanged","point_ru":"Flash Attention вычисляет математически тот же результат attention (softmax(QK^T/sqrt(d))V), не меняя формулу."},{"id":"how_it_changes","point_ru":"Меняется способ вычисления: блочное (tiled) вычисление и fused-кернел вместо материализации полной матрицы attention."},{"id":"memory_benefit","point_ru":"За счёт этого не хранится полная N×N матрица attention в памяти — память растёт линейно, а не квадратично от длины последовательности."},{"id":"speed_benefit","point_ru":"Ускорение достигается за счёт меньшего числа обращений к медленной HBM-памяти GPU (IO-aware алгоритм), а не за счёт меньшего числа арифметических операций."}],"reference_explanation_ru":"Flash Attention не меняет математику attention — результат тот же softmax(QK^T/√d)V. Меняется способ вычисления: блочный (tiled) fused-кернел, который не материализует полную N×N матрицу attention в памяти GPU. Это даёт линейный, а не квадратичный расход памяти по длине последовательности и ускорение за счёт меньшего числа обращений к медленной HBM-памяти, а не за счёт уменьшения числа арифметических операций.","follow_ups":["Почему обращения к HBM-памяти являются узким местом, а не сами арифметические операции?","Как Flash Attention влияет на возможность работать с более длинным контекстом?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"d847e19e-675b-5ef1-98fe-071a31a1e3d4","idempotency_key":"backfill:mltech_005:r1","content_hash":"f4829804912fa797516ff546ab6bf2221c8e8ae52016ce5352087506c9c53917"},{"question_key":"mltech_006","track_id":"ml_technical","topic_id":"transformers_llm","question_ru":"Чем self-attention отличается от attention в классическом encoder-decoder (seq2seq) механизме?","difficulty":"medium","tags":["self_attention","seq2seq","encoder_decoder"],"rubric_points":[{"id":"self_attention_scope","point_ru":"Self-attention считает Q, K, V из одной и той же последовательности — токены смотрят друг на друга внутри одного набора."},{"id":"classic_attention_scope","point_ru":"Классический seq2seq attention (например Bahdanau/Luong) считает attention между декодером (Q) и энкодером (K, V) — это cross-attention между двумя разными последовательностями."},{"id":"purpose_difference","point_ru":"Self-attention строит контекстуализированное представление внутри последовательности; классический attention передаёт информацию из энкодера в декодер на каждом шаге генерации."},{"id":"architecture_context","point_ru":"В трансформере оба вида присутствуют: self-attention в энкодере и декодере плюс cross-attention между ними."}],"reference_explanation_ru":"Self-attention вычисляет Q, K и V из одной последовательности — токены обращают внимание друг на друга внутри одного набора данных. Классический attention в seq2seq (например, Bahdanau или Luong) — это cross-attention между декодером (запрос) и энкодером (ключи и значения), передающий информацию из входной последовательности на каждом шаге генерации выхода. В трансформере есть оба механизма: self-attention внутри энкодера и декодера, и cross-attention между ними.","follow_ups":["Где именно в декодере трансформера используется cross-attention к энкодеру?","Почему self-attention даёт более параллелизуемое вычисление, чем рекуррентный attention в RNN?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"930f3bb2-8ecb-56c9-b1a6-7ec93388a692","idempotency_key":"backfill:mltech_006:r1","content_hash":"0797f458a9fa50f8056ab50d0201d3949d2dbc2d1ac3532c70d2478046df39be"},{"question_key":"mltech_007","track_id":"ml_technical","topic_id":"finetuning_peft","question_ru":"Как устроена LoRA: матрицы A и B, ранг, инициализация и применение на inference?","difficulty":"hard","tags":["lora","peft","finetuning"],"rubric_points":[{"id":"decomposition","point_ru":"LoRA замораживает исходную матрицу весов W и добавляет к ней низкоранговое обновление: W' = W + B·A, где A и B — маленькие матрицы ранга r << d."},{"id":"rank_role","point_ru":"Ранг r — гиперпараметр, задающий размер обучаемых матриц и компромисс между качеством адаптации и числом обучаемых параметров."},{"id":"initialization","point_ru":"Обычно A инициализируется случайно (например, гауссовым шумом), а B — нулями, так что в начале обучения B·A = 0 и модель стартует как исходная предобученная."},{"id":"inference_application","point_ru":"На inference B·A можно либо оставить отдельным адаптером (легко переключать), либо слить (merge) в исходные веса W, чтобы не терять скорость по сравнению с базовой моделью."}],"reference_explanation_ru":"LoRA замораживает исходные веса W и добавляет к ним низкоранговое обновление B·A, где A и B — матрицы малого ранга r, а обучаются только они. Ранг r задаёт компромисс между выразительностью адаптации и числом обучаемых параметров. Инициализация: A — случайная, B — нулевая, поэтому в начале обучения добавка равна нулю и модель совпадает с базовой. На inference адаптер B·A можно применять отдельно (для быстрого переключения между задачами) или слить в исходные веса, чтобы не терять скорость инференса.","follow_ups":["Почему инициализация B нулями важна для стабильности старта обучения?","К каким весам трансформера чаще всего применяют LoRA (например, к каким проекциям attention)?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"af764007-25fe-5494-b4ac-062637dc0f9b","idempotency_key":"backfill:mltech_007:r1","content_hash":"d7fc97332fa85a6f61d0f3cb9f7f6946e9ea7e15bfa3cb93f2609c3bc67da7fc"},{"question_key":"mltech_008","track_id":"ml_technical","topic_id":"transformers_llm","question_ru":"Зачем нужны Multi-Head Attention и Multi-Query Attention, и какие у них компромиссы?","difficulty":"hard","tags":["multi_head_attention","multi_query_attention","kv_cache"],"rubric_points":[{"id":"multi_head_purpose","point_ru":"Multi-Head Attention считает несколько параллельных attention-голов с разными проекциями Q/K/V, позволяя модели учитывать разные типы зависимостей одновременно."},{"id":"multi_head_cost","point_ru":"Каждая голова в MHA хранит собственные K и V, что увеличивает объём KV-cache пропорционально числу голов."},{"id":"mqa_idea","point_ru":"Multi-Query Attention использует общие K и V на все головы (разные только Q), что резко уменьшает размер KV-cache и ускоряет инференс."},{"id":"tradeoff","point_ru":"Компромисс MQA — экономия памяти и latency ценой потенциально меньшей выразительности/качества по сравнению с полным MHA; GQA (grouped-query attention) — промежуточный вариант."}],"reference_explanation_ru":"Multi-Head Attention считает несколько attention-голов параллельно с разными проекциями Q/K/V, что позволяет модели одновременно учитывать разные виды зависимостей между токенами. Цена — каждая голова хранит свои K и V, и KV-cache растёт пропорционально числу голов. Multi-Query Attention делает K и V общими для всех голов (различаются только Q), сильно уменьшая KV-cache и ускоряя инференс, но потенциально немного теряя в качестве по сравнению с полным MHA; grouped-query attention — компромисс между этими двумя крайностями.","follow_ups":["Как GQA (grouped-query attention) располагается между MHA и MQA?","Почему уменьшение KV-cache особенно важно при батчевом инференсе с длинным контекстом?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"b8329638-71a7-5ccf-b20a-8fa9cb2f815b","idempotency_key":"backfill:mltech_008:r1","content_hash":"785f034af9d39fc5c294211206a5dbda527ec44fa65a8bf24364e1933d95564a"},{"question_key":"mltech_009","track_id":"ml_technical","topic_id":"dl_training","question_ru":"Какие виды регуляризации нейросетей есть и какой конкретный дефект обучения лечит каждый метод?","difficulty":"easy","tags":["regularization","overfitting","generalization"],"rubric_points":[{"id":"l2_weight_decay","point_ru":"L2-регуляризация (weight decay) штрафует большие веса, борется с переобучением, сглаживая функцию модели."},{"id":"dropout","point_ru":"Dropout случайно зануляет часть активаций на train, борется с ко-адаптацией нейронов и переобучением."},{"id":"early_stopping","point_ru":"Early stopping останавливает обучение при росте ошибки на валидации, борется с переобучением на поздних эпохах."},{"id":"data_augmentation","point_ru":"Аугментация данных увеличивает эффективное разнообразие обучающей выборки, борется с переобучением при ограниченных данных."}],"reference_explanation_ru":"Основные виды регуляризации: L2/weight decay — штрафует большие веса и сглаживает функцию модели против переобучения; dropout — случайно зануляет активации на train, борясь с ко-адаптацией нейронов; early stopping — останавливает обучение при росте ошибки на валидации; аугментация данных — расширяет эффективное разнообразие обучающей выборки. Каждый метод атакует переобучение с разной стороны — веса, совместную адаптацию нейронов, момент остановки или сами данные.","follow_ups":["Почему dropout выключается на инференсе и как компенсируется масштаб активаций?","Чем L1-регуляризация отличается от L2 по влиянию на веса?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"e6849141-d156-506a-801b-16cafc2319c1","idempotency_key":"backfill:mltech_009:r1","content_hash":"3815090ab6d27090820942e9a1b709799427c5eb1dac8bb5b70789f17912a745"},{"question_key":"mltech_010","track_id":"ml_technical","topic_id":"dl_training","question_ru":"Как dropout работает во время обучения и почему он выключается на инференсе?","difficulty":"easy","tags":["dropout","train_vs_inference","regularization"],"rubric_points":[{"id":"train_mechanism","point_ru":"На train dropout случайно зануляет часть нейронов/активаций с вероятностью p на каждом forward-проходе."},{"id":"purpose","point_ru":"Это мешает нейронам чрезмерно полагаться друг на друга (ко-адаптации) и работает как регуляризация против переобучения."},{"id":"inference_off","point_ru":"На inference dropout выключают, чтобы предсказание было детерминированным и использовало всю сеть целиком."},{"id":"scaling","point_ru":"Чтобы ожидаемая величина активаций совпадала между train и inference, применяют масштабирование (inverted dropout: деление на (1-p) на train, либо умножение на (1-p) на inference)."}],"reference_explanation_ru":"На train dropout случайно зануляет часть активаций с вероятностью p на каждом forward-проходе, что мешает нейронам чрезмерно полагаться друг на друга и работает как регуляризация. На inference dropout выключают, чтобы предсказание было детерминированным и использовало всю сеть. Чтобы масштаб активаций совпадал между train и inference, используют inverted dropout — масштабирование оставшихся активаций на train на 1/(1-p).","follow_ups":["Что такое inverted dropout и зачем нужно масштабирование на train?","Как dropout соотносится с DropPath/Stochastic Depth в глубоких сетях?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"5daaab93-1992-5dca-99db-13e7d397797c","idempotency_key":"backfill:mltech_010:r1","content_hash":"a0f4131acb9f66dd2205b71df25e5d03cca87c2fc2a8ef2db30ecf992204876a"},{"question_key":"mltech_011","track_id":"ml_technical","topic_id":"transformers_llm","question_ru":"Как устроен трансформер целиком: encoder/decoder, Q/K/V, attention, FFN, residual connections, normalization?","difficulty":"medium","tags":["transformer_architecture","attention","ffn","residual","normalization"],"rubric_points":[{"id":"qkv","point_ru":"Q, K, V — проекции входных эмбеддингов; attention считает веса как softmax(QK^T/√d) и взвешивает V."},{"id":"encoder_decoder_blocks","point_ru":"Энкодер строит представление входа через self-attention + FFN; декодер дополнительно использует masked self-attention (авторегрессия) и cross-attention к энкодеру."},{"id":"ffn","point_ru":"После attention в каждом блоке стоит position-wise feed-forward сеть (обычно с расширением размерности и нелинейностью), применяемая к каждому токену независимо."},{"id":"residual_and_norm","point_ru":"Residual connections (skip-соединения) вокруг attention и FFN плюс normalization (LayerNorm, pre-norm или post-norm) стабилизируют обучение глубоких стеков блоков."}],"reference_explanation_ru":"Трансформер строится из блоков, каждый из которых содержит self-attention и position-wise feed-forward сеть (FFN), обёрнутые в residual connections и normalization (LayerNorm). Attention считает Q, K, V из входа и взвешивает V весами softmax(QK^T/√d). Энкодер применяет self-attention и FFN к входу; декодер дополнительно использует masked self-attention (чтобы не заглядывать вперёд при генерации) и cross-attention к выходу энкодера. Residual connections и normalization нужны, чтобы градиенты стабильно проходили через глубокий стек блоков.","follow_ups":["В чём разница между pre-norm и post-norm расположением LayerNorm в блоке трансформера?","Зачем в decoder self-attention нужна маска (causal mask)?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"8986f217-6009-5a08-80ac-104e1fd579b4","idempotency_key":"backfill:mltech_011:r1","content_hash":"f1cdc731ae5e029172c35372a17b3e59d8fefabbddd215f8d1f32f6a29c0f889"},{"question_key":"mltech_012","track_id":"ml_technical","topic_id":"dl_training","question_ru":"Чем AdamW отличается от Adam, а Momentum — от обычного SGD?","difficulty":"medium","tags":["optimizers","adam","adamw","sgd","momentum"],"rubric_points":[{"id":"adam_mechanism","point_ru":"Adam хранит оценки первого и второго моментов градиента (аналог momentum + адаптивный per-parameter learning rate) и использует их для обновления весов."},{"id":"adam_weight_decay_issue","point_ru":"В классическом Adam weight decay реализован как L2-штраф внутри градиента, из-за чего он смешивается с адаптивным масштабированием и работает не совсем как ожидаемая регуляризация."},{"id":"adamw_fix","point_ru":"AdamW отделяет weight decay от градиентного шага (decoupled weight decay) — вычитает weight decay из весов напрямую, а не через градиент, что даёт более предсказуемую регуляризацию."},{"id":"momentum_vs_sgd","point_ru":"Momentum добавляет к обычному SGD накопление скользящего среднего прошлых градиентов (velocity), что ускоряет движение в устойчивом направлении и сглаживает колебания по сравнению с чистым SGD."}],"reference_explanation_ru":"Adam хранит оценки первого и второго моментов градиента и адаптирует learning rate по каждому параметру. В классическом Adam weight decay реализован как L2-штраф внутри градиента и смешивается с адаптивным масштабированием, что делает регуляризацию менее предсказуемой. AdamW отделяет weight decay от градиентного шага (decoupled weight decay), вычитая его из весов напрямую. Momentum добавляет к обычному SGD накопление скользящего среднего прошлых градиентов (velocity), что ускоряет движение в устойчивом направлении и сглаживает колебания по сравнению с шагом чистого SGD, который использует только текущий градиент.","follow_ups":["Почему decoupled weight decay в AdamW считается более честной регуляризацией?","Что произойдёт с обучением, если momentum слишком большой?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"ed3c8c68-cce9-5057-955e-93c7288baebe","idempotency_key":"backfill:mltech_012:r1","content_hash":"687579287d4ccd011a1aa0c6f74cb8c581aaa61632a750a65f1cfe5927c69d7c"},{"question_key":"mltech_013","track_id":"ml_technical","topic_id":"ml_fundamentals","question_ru":"Почему возникают vanishing и exploding gradients, как их диагностировать и как исправлять?","difficulty":"medium","tags":["vanishing_gradients","exploding_gradients","backprop","training_diagnostics"],"rubric_points":[{"id":"cause","point_ru":"При backprop градиент — произведение множества производных по слоям; если эти множители систематически <1 (или >1), произведение экспоненциально затухает (или взрывается) с глубиной сети."},{"id":"vanishing_symptoms","point_ru":"Признаки vanishing gradients: ранние слои почти не обучаются, loss стагнирует, веса первых слоёв почти не меняются."},{"id":"exploding_symptoms","point_ru":"Признаки exploding gradients: loss резко скачет или становится NaN/Inf, норма градиентов аномально большая."},{"id":"fixes","point_ru":"Исправления: подходящая инициализация весов, нормализация (BatchNorm/LayerNorm), residual connections, gradient clipping (для взрыва), смена функции активации (например ReLU вместо sigmoid/tanh)."}],"reference_explanation_ru":"При обратном распространении градиент по ранним слоям — произведение множества локальных производных. Если эти множители систематически меньше единицы, произведение экспоненциально затухает с глубиной (vanishing gradients); если больше единицы — экспоненциально растёт (exploding gradients). Диагностика: vanishing — ранние слои почти не обучаются, loss стагнирует; exploding — loss скачет или становится NaN, норма градиента аномально велика. Лечение: подходящая инициализация, нормализация слоёв, residual connections, gradient clipping (при взрыве) и функции активации без насыщения (например ReLU вместо sigmoid/tanh).","follow_ups":["Как residual connections конкретно помогают против vanishing gradients?","Что такое gradient clipping и как выбирают порог для него?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"23501151-0456-525f-ad48-a10e99084c6d","idempotency_key":"backfill:mltech_013:r1","content_hash":"e0552e3d49362f903deb57066eb45023bb3f8f2e6c8d50f801fdf8d3f4fbc644"},{"question_key":"mltech_014","track_id":"ml_technical","topic_id":"inference_mlops","question_ru":"Что именно хранит KV-cache, почему кэшируют K и V, а не Q, и как это влияет на память и latency?","difficulty":"hard","tags":["kv_cache","inference","latency","memory"],"rubric_points":[{"id":"what_is_cached","point_ru":"KV-cache хранит вычисленные ключи (K) и значения (V) для всех уже сгенерированных токенов, чтобы не пересчитывать их заново на каждом новом шаге генерации."},{"id":"why_not_q","point_ru":"Q нужен только для текущего шага (запрос от нового токена к прошлому контексту), а не переиспользуется для будущих шагов, поэтому кэшировать его не нужно; K и V от прошлых токенов остаются неизменными и переиспользуются на каждом новом шаге."},{"id":"memory_impact","point_ru":"Размер KV-cache растёт линейно с длиной последовательности и числом слоёв/голов, и может стать доминирующим потребителем GPU-памяти при длинном контексте и большом батче."},{"id":"latency_impact","point_ru":"Без KV-cache пришлось бы пересчитывать attention по всей истории на каждом шаге генерации (квадратичная стоимость); с кэшем каждый новый токен считается за счёт одного дополнительного шага, что резко снижает latency автогрегрессивной генерации."}],"reference_explanation_ru":"KV-cache хранит вычисленные ключи (K) и значения (V) для уже сгенерированных токенов, чтобы не пересчитывать attention по всей истории заново на каждом шаге. Q кэшировать не нужно — он представляет запрос текущего шага и не переиспользуется в будущем, тогда как K и V прошлых токенов не меняются и годятся для всех последующих шагов. Размер KV-cache растёт линейно с длиной последовательности, числом слоёв и голов и может стать основным потребителем GPU-памяти при длинном контексте. Без кэша генерация каждого нового токена требовала бы пересчёта attention по всей истории, что резко увеличивает latency автогрегрессивной генерации.","follow_ups":["Как Multi-Query или Grouped-Query Attention уменьшают размер KV-cache?","Что такое continuous batching и как он взаимодействует с KV-cache в системах вроде vLLM?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"0c3a2be7-c2fa-58de-a325-6cf1c89c6b8c","idempotency_key":"backfill:mltech_014:r1","content_hash":"1e8a1373409cd92e30e366e723c5984e319eaaabc521cc94810bb30eb0c632b4"},{"question_key":"mltech_015","track_id":"ml_technical","topic_id":"finetuning_peft","question_ru":"Чем QLoRA отличается от LoRA и что именно в QLoRA квантуется?","difficulty":"hard","tags":["qlora","lora","quantization","peft"],"rubric_points":[{"id":"base_model_quantized","point_ru":"В QLoRA замороженная базовая модель хранится в низкобитном квантизованном формате (обычно 4-bit, NormalFloat4), а не в FP16/BF16 как в обычной LoRA."},{"id":"adapters_stay_precise","point_ru":"Обучаемые LoRA-адаптеры (матрицы A и B) остаются в более высокой точности (например BF16) и обучаются поверх квантизованной базовой модели."},{"id":"memory_benefit","point_ru":"Основной выигрыш QLoRA — резкое снижение памяти для хранения замороженных весов, что позволяет дообучать модели существенно большего размера на одной GPU."},{"id":"dequantization_at_compute","point_ru":"Во время forward/backward квантизованные веса на лету деквантизуются в вычислительный формат более высокой точности для матричного умножения, а хранятся при этом в низкобитном виде."}],"reference_explanation_ru":"В обычной LoRA замороженная базовая модель хранится в исходной точности (например FP16/BF16), и обучаются только маленькие матрицы-адаптеры A и B. QLoRA дополнительно квантует саму замороженную базовую модель в низкобитный формат (обычно 4-bit NormalFloat4), тогда как LoRA-адаптеры остаются в более высокой точности и обучаются поверх квантизованных весов. Во время вычислений квантизованные веса на лету деквантизуются для матричного умножения, а хранятся в памяти в низкобитном виде. Основной эффект — резкое снижение требований к памяти, что позволяет дообучать намного более крупные модели на одной GPU.","follow_ups":["Что такое NormalFloat4 и почему он подходит для весов с нормальным распределением?","Почему LoRA-адаптеры в QLoRA не квантуют так же агрессивно, как базовую модель?"],"rubric_version":"ml-technical-v1","source_kind":"owner_authored","source_label":"Founder interview preparation notes","source_uri_public":null,"source_fingerprint":"21ae63b7e034a5aee31b97dbfde1b59464388418600ec10cf58a7e769c6d2dbc","derivation_kind":"original","publication_scope":"internal_only","license_note":"Owner-authored preparation material; no third-party raw text.","model_id":null,"prompt_version":null,"revision_id":"8c73c8f5-90f9-5bcb-8203-52bab0d4e4ef","idempotency_key":"backfill:mltech_015:r1","content_hash":"8e2d1dc3a3bd88125c04afc43ed5dace05089f80f74b210b840b68917f1eea78"}]$fixture$::jsonb);

do $$
declare
  fixture_count integer;
begin
  select jsonb_array_length(payload) into fixture_count from mlq014_fixture;
  if fixture_count <> 15 then
    raise exception '014 question fixture must contain exactly 15 rows, got %', fixture_count
      using errcode = '22023';
  end if;
end $$;

create temp table mlq014_expected on commit drop as
select
  (item->>'revision_id')::uuid as id,
  item->>'question_key' as question_key,
  1::integer as revision_no,
  'ml_technical'::varchar(40) as track_id,
  'approved'::varchar(20) as status,
  item->>'topic_id' as topic_id,
  item->>'question_ru' as question_ru,
  item->>'difficulty' as difficulty,
  item->'tags' as tags,
  item->'rubric_points' as rubric_points,
  item->>'reference_explanation_ru' as reference_explanation_ru,
  item->'follow_ups' as follow_ups,
  item->>'rubric_version' as rubric_version,
  item->>'source_kind' as source_kind,
  item->>'source_label' as source_label,
  nullif(item->>'source_uri_public', '') as source_uri_public,
  item->>'source_fingerprint' as source_fingerprint,
  item->>'derivation_kind' as derivation_kind,
  item->>'publication_scope' as publication_scope,
  item->>'license_note' as license_note,
  nullif(item->>'model_id', '') as model_id,
  nullif(item->>'prompt_version', '') as prompt_version,
  item->>'idempotency_key' as idempotency_key,
  item->>'content_hash' as content_hash,
  'migration:014'::varchar(160) as created_by,
  '2026-07-21T00:00:00+00:00'::timestamptz as created_at,
  'owner:checked-in-pack'::varchar(160) as approved_by,
  '2026-07-21T00:00:00+00:00'::timestamptz as approved_at
from mlq014_fixture
cross join lateral jsonb_array_elements(payload) as fixture(item);

do $$
begin
  if exists (
    select 1
    from mlq014_expected expected
    join ml_question_revisions actual
      on actual.question_key = expected.question_key
     and actual.revision_no = expected.revision_no
    where actual.id is distinct from expected.id
       or actual.content_hash is distinct from expected.content_hash
  ) then
    raise exception '014 question backfill hash/id mismatch; refusing split-brain rerun'
      using errcode = '23505';
  end if;
end $$;

insert into ml_question_revisions (
  id, question_key, revision_no, supersedes_id, track_id, status, topic_id,
  question_ru, difficulty, tags, rubric_points, reference_explanation_ru,
  follow_ups, rubric_version, source_kind, source_label, source_uri_public,
  source_fingerprint, derivation_kind, publication_scope, license_note,
  model_id, prompt_version, idempotency_key, content_hash, created_by,
  created_at, approved_by, approved_at
)
select
  id, question_key, revision_no, null::uuid, track_id, status, topic_id,
  question_ru, difficulty, tags, rubric_points, reference_explanation_ru,
  follow_ups, rubric_version, source_kind, source_label, source_uri_public,
  source_fingerprint, derivation_kind, publication_scope, license_note,
  model_id, prompt_version, idempotency_key, content_hash, created_by,
  created_at, approved_by, approved_at
from mlq014_expected
on conflict (question_key, revision_no) do nothing;

-- The checked-in pack already passed focused rubric and provenance tests.
-- Record that migration basis explicitly rather than pretending a new model review ran.
insert into ml_question_reviews (
  id, question_revision_id, review_kind, verdict, findings, reviewer_type,
  reviewer_id, model_id, prompt_version, input_content_hash, created_at
)
select
  (
    substr(md5(expected.id::text || ':' || kind.review_kind), 1, 8) || '-' ||
    substr(md5(expected.id::text || ':' || kind.review_kind), 9, 4) || '-' ||
    substr(md5(expected.id::text || ':' || kind.review_kind), 13, 4) || '-' ||
    substr(md5(expected.id::text || ':' || kind.review_kind), 17, 4) || '-' ||
    substr(md5(expected.id::text || ':' || kind.review_kind), 21, 12)
  )::uuid,
  expected.id,
  kind.review_kind,
  'pass',
  '[]'::jsonb,
  case when kind.review_kind = 'schema' then 'deterministic' else 'human' end,
  case
    when kind.review_kind = 'schema' then 'ml-question-schema-v1'
    else 'owner:checked-in-pack'
  end,
  null,
  'checked-in-pack-v1',
  expected.content_hash,
  expected.created_at
from mlq014_expected expected
cross join (values ('schema'), ('technical'), ('source_ip')) as kind(review_kind)
on conflict (id) do nothing;

alter table ml_technical_session_items
  add column if not exists question_revision_id uuid;
alter table ml_technical_attempts
  add column if not exists question_revision_id uuid;

update ml_technical_session_items item
set question_revision_id = revision.id
from ml_question_revisions revision
where item.question_revision_id is null
  and revision.question_key = item.question_id
  and revision.revision_no = 1;

update ml_technical_attempts attempt
set question_revision_id = revision.id
from ml_question_revisions revision
where attempt.question_revision_id is null
  and revision.question_key = attempt.question_id
  and revision.revision_no = 1;

do $$
declare
  missing_items integer;
  missing_attempts integer;
begin
  select count(*) into missing_items
  from ml_technical_session_items
  where question_revision_id is null;

  select count(*) into missing_attempts
  from ml_technical_attempts
  where question_revision_id is null;

  if missing_items <> 0 or missing_attempts <> 0 then
    raise exception '014 cannot bind exact revision: % session item(s), % attempt(s)',
      missing_items, missing_attempts using errcode = '23503';
  end if;
end $$;

do $$ begin
  alter table ml_technical_session_items
    add constraint ml_technical_session_items_question_revision_fkey
    foreign key (question_revision_id) references ml_question_revisions(id) on delete restrict;
exception when duplicate_object then null;
end $$;

do $$ begin
  alter table ml_technical_attempts
    add constraint ml_technical_attempts_question_revision_fkey
    foreign key (question_revision_id) references ml_question_revisions(id) on delete restrict;
exception when duplicate_object then null;
end $$;

alter table ml_technical_session_items
  alter column question_revision_id set not null;
alter table ml_technical_attempts
  alter column question_revision_id set not null;

create index if not exists ml_technical_session_items_question_revision_idx
  on ml_technical_session_items(question_revision_id);
create index if not exists ml_technical_attempts_question_revision_idx
  on ml_technical_attempts(question_revision_id);

create or replace function ml_question_revision_immutable_guard()
returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    if new.revision_no = 1 and new.supersedes_id is not null then
      raise exception 'first ml_question_revision cannot supersede another revision'
        using errcode = '55000';
    end if;
    if new.revision_no > 1 then
      if new.supersedes_id is null or not exists (
        select 1
        from ml_question_revisions parent
        where parent.id = new.supersedes_id
          and parent.question_key = new.question_key
          and parent.status = 'approved'
      ) then
        raise exception 'new ml_question_revision must supersede the current approved revision'
          using errcode = '55000';
      end if;
    end if;

    if new.status = 'draft' and row(
      new.approved_by, new.approved_at, new.retired_by,
      new.retired_at, new.retirement_reason
    ) is distinct from row(null, null, null, null, null) then
      raise exception 'draft ml_question_revision cannot have lifecycle audit fields'
        using errcode = '55000';
    end if;
    if new.status = 'approved' and (
      new.approved_by is null or new.approved_at is null
      or new.retired_by is not null or new.retired_at is not null
      or new.retirement_reason is not null
    ) then
      raise exception 'approved ml_question_revision requires immutable approval audit fields'
        using errcode = '55000';
    end if;
    if new.status = 'retired' and (
      new.retired_by is null or new.retired_at is null
      or new.retirement_reason is null
    ) then
      raise exception 'retired ml_question_revision requires retirement audit fields'
        using errcode = '55000';
    end if;
    return new;
  end if;

  if tg_op = 'DELETE' then
    raise exception 'ml_question_revisions are never deleted' using errcode = '55000';
  end if;

  if row(
    new.question_key, new.revision_no, new.supersedes_id, new.track_id,
    new.topic_id, new.question_ru, new.difficulty, new.tags, new.rubric_points,
    new.reference_explanation_ru, new.follow_ups, new.rubric_version,
    new.source_kind, new.source_label, new.source_uri_public,
    new.source_fingerprint, new.derivation_kind, new.publication_scope,
    new.license_note, new.model_id, new.prompt_version, new.idempotency_key,
    new.content_hash, new.created_by, new.created_at
  ) is distinct from row(
    old.question_key, old.revision_no, old.supersedes_id, old.track_id,
    old.topic_id, old.question_ru, old.difficulty, old.tags, old.rubric_points,
    old.reference_explanation_ru, old.follow_ups, old.rubric_version,
    old.source_kind, old.source_label, old.source_uri_public,
    old.source_fingerprint, old.derivation_kind, old.publication_scope,
    old.license_note, old.model_id, old.prompt_version, old.idempotency_key,
    old.content_hash, old.created_by, old.created_at
  ) then
    raise exception 'ml_question_revision content is immutable' using errcode = '55000';
  end if;

  if old.status = new.status then
    if row(
      new.approved_by, new.approved_at, new.retired_by,
      new.retired_at, new.retirement_reason
    ) is distinct from row(
      old.approved_by, old.approved_at, old.retired_by,
      old.retired_at, old.retirement_reason
    ) then
      raise exception 'ml_question_revision audit fields are immutable without a lifecycle transition'
        using errcode = '55000';
    end if;
    return new;
  end if;

  if old.status = 'draft' and new.status = 'approved' then
    if new.approved_by is null or new.approved_at is null
       or new.retired_by is not null or new.retired_at is not null
       or new.retirement_reason is not null then
      raise exception 'draft to approved requires only approval audit fields'
        using errcode = '55000';
    end if;
    return new;
  end if;

  if old.status = 'draft' and new.status = 'retired' then
    if new.approved_by is not null or new.approved_at is not null
       or new.retired_by is null or new.retired_at is null
       or new.retirement_reason is null then
      raise exception 'draft to retired requires only retirement audit fields'
        using errcode = '55000';
    end if;
    return new;
  end if;

  if old.status = 'approved' and new.status = 'retired' then
    if row(new.approved_by, new.approved_at) is distinct from
       row(old.approved_by, old.approved_at)
       or new.retired_by is null or new.retired_at is null
       or new.retirement_reason is null then
      raise exception 'approved to retired must preserve approval and add retirement audit fields'
        using errcode = '55000';
    end if;
    return new;
  end if;

  raise exception 'illegal ml_question_revision lifecycle transition: % to %',
    old.status, new.status using errcode = '55000';
end $$;

drop trigger if exists ml_question_revision_immutable_guard_trigger
  on ml_question_revisions;
create trigger ml_question_revision_immutable_guard_trigger
before insert or update or delete on ml_question_revisions
for each row execute function ml_question_revision_immutable_guard();

create or replace function ml_question_review_append_only_guard()
returns trigger language plpgsql as $$
begin
  raise exception 'ml_question_reviews are append-only' using errcode = '55000';
end $$;

drop trigger if exists ml_question_review_append_only_guard_trigger
  on ml_question_reviews;
create trigger ml_question_review_append_only_guard_trigger
before update or delete on ml_question_reviews
for each row execute function ml_question_review_append_only_guard();

commit;
