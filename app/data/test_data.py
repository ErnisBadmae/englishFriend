"""
Тестовые данные для справочников.
Этот файл содержит начальные данные для заполнения справочников эмоций, тем и акцентов.
"""

# Тестовые эмоции
EMOTIONS_DATA = [
    {"code": "joy", "name_ru": "Радость", "valence": 4, "arousal": 4},
    {"code": "sadness", "name_ru": "Грусть", "valence": -3, "arousal": 2},
    {"code": "anger", "name_ru": "Гнев", "valence": -4, "arousal": 5},
    {"code": "fear", "name_ru": "Страх", "valence": -3, "arousal": 5},
    {"code": "surprise", "name_ru": "Удивление", "valence": 2, "arousal": 4},
    {"code": "disgust", "name_ru": "Отвращение", "valence": -4, "arousal": 3},
    {"code": "calm", "name_ru": "Спокойствие", "valence": 2, "arousal": 1},
    {"code": "excitement", "name_ru": "Волнение", "valence": 4, "arousal": 5},
    {"code": "frustration", "name_ru": "Разочарование", "valence": -2, "arousal": 3},
    {"code": "confidence", "name_ru": "Уверенность", "valence": 3, "arousal": 2},
    {"code": "nervousness", "name_ru": "Нервозность", "valence": -1, "arousal": 4},
    {"code": "satisfaction", "name_ru": "Удовлетворение", "valence": 3, "arousal": 2},
]

# Тестовые темы
TOPICS_DATA = [
    # Основные категории
    {"slug": "daily-life", "display_name": "Повседневная жизнь", "parent_id": None},
    {"slug": "work-career", "display_name": "Работа и карьера", "parent_id": None},
    {"slug": "education", "display_name": "Образование", "parent_id": None},
    {"slug": "travel", "display_name": "Путешествия", "parent_id": None},
    {"slug": "hobbies", "display_name": "Хобби и интересы", "parent_id": None},
    {"slug": "family", "display_name": "Семья и отношения", "parent_id": None},
    {"slug": "health", "display_name": "Здоровье и спорт", "parent_id": None},
    {"slug": "technology", "display_name": "Технологии", "parent_id": None},
    {"slug": "culture", "display_name": "Культура и искусство", "parent_id": None},
    {"slug": "food", "display_name": "Еда и кулинария", "parent_id": None},
    
    # Подтемы для повседневной жизни
    {"slug": "morning-routine", "display_name": "Утренняя рутина", "parent_id": "daily-life"},
    {"slug": "shopping", "display_name": "Покупки", "parent_id": "daily-life"},
    {"slug": "transportation", "display_name": "Транспорт", "parent_id": "daily-life"},
    {"slug": "weather", "display_name": "Погода", "parent_id": "daily-life"},
    
    # Подтемы для работы
    {"slug": "job-interview", "display_name": "Собеседование", "parent_id": "work-career"},
    {"slug": "meetings", "display_name": "Встречи", "parent_id": "work-career"},
    {"slug": "projects", "display_name": "Проекты", "parent_id": "work-career"},
    {"slug": "colleagues", "display_name": "Коллеги", "parent_id": "work-career"},
    
    # Подтемы для образования
    {"slug": "english-learning", "display_name": "Изучение английского", "parent_id": "education"},
    {"slug": "university", "display_name": "Университет", "parent_id": "education"},
    {"slug": "exams", "display_name": "Экзамены", "parent_id": "education"},
    {"slug": "homework", "display_name": "Домашние задания", "parent_id": "education"},
    
    # Подтемы для путешествий
    {"slug": "vacation", "display_name": "Отпуск", "parent_id": "travel"},
    {"slug": "hotels", "display_name": "Отели", "parent_id": "travel"},
    {"slug": "sightseeing", "display_name": "Достопримечательности", "parent_id": "travel"},
    {"slug": "local-culture", "display_name": "Местная культура", "parent_id": "travel"},
]

# Тестовые акценты
ACCENTS_DATA = [
    {"code": "american", "display_name": "Американский английский"},
    {"code": "british", "display_name": "Британский английский"},
    {"code": "australian", "display_name": "Австралийский английский"},
    {"code": "canadian", "display_name": "Канадский английский"},
    {"code": "irish", "display_name": "Ирландский английский"},
    {"code": "scottish", "display_name": "Шотландский английский"},
    {"code": "neutral", "display_name": "Нейтральный акцент"},
]

# Тестовые пользователи
USERS_DATA = [
    {
        "telegram_id": 123456789,
        "username": "test_user_1",
        "language_level": "B1",
        "accent_pref": "american"
    },
    {
        "telegram_id": 987654321,
        "username": "test_user_2", 
        "language_level": "A2",
        "accent_pref": "british"
    },
    {
        "telegram_id": 555666777,
        "username": "test_user_3",
        "language_level": "C1",
        "accent_pref": "neutral"
    }
]

# Тестовые сессии
SESSIONS_DATA = [
    {
        "user_id": 1,
        "lang_code": "en",
        "topics_detected": {"daily-life": 0.8, "weather": 0.6},
        "emotion_detected": "calm",
        "grammar_score": 7.5,
        "pronunciation_score": 8.0
    },
    {
        "user_id": 2,
        "lang_code": "en", 
        "topics_detected": {"work-career": 0.9, "meetings": 0.7},
        "emotion_detected": "confidence",
        "grammar_score": 6.0,
        "pronunciation_score": 6.5
    }
]

# Тестовые реплики
UTTERANCES_DATA = [
    {
        "session_id": "session_1",
        "speaker": "user",
        "t_start_ms": 0,
        "t_end_ms": 3000,
        "text": "Good morning! How are you today?",
        "emotion_code": "joy",
        "emotion_score": 0.8,
        "grammar_score": 8.0,
        "pronunciation_score": 7.5
    },
    {
        "session_id": "session_1", 
        "speaker": "assistant",
        "t_start_ms": 3000,
        "t_end_ms": 6000,
        "text": "Good morning! I'm doing great, thank you for asking. How about you?",
        "emotion_code": "joy",
        "emotion_score": 0.9,
        "grammar_score": 9.0,
        "pronunciation_score": 9.0
    }
]

# Тестовая обратная связь
FEEDBACK_DATA = [
    {
        "session_id": "session_1",
        "overall_grammar": 7.5,
        "overall_pronunciation": 8.0,
        "summary_md": "Great job! Your pronunciation was very clear today.",
        "tips_md": "Try to work on your intonation in questions.",
        "grammar_tips": "Remember to use 'How are you?' instead of 'How you are?'",
        "pronunciation_tips": "The 'th' sound in 'thank you' was perfect!"
    }
]

# Тестовые исправления
CORRECTIONS_DATA = [
    {
        "session_id": "session_1",
        "user_text": "I go to work yesterday",
        "corrected_text": "I went to work yesterday",
        "rule_tag": "past_simple",
        "explanation_md": "Use past simple tense for completed actions in the past."
    }
]

# Тестовые интересы
INTERESTS_DATA = [
    {"user_id": 1, "topic_id": "daily-life", "weight": 8.5},
    {"user_id": 1, "topic_id": "weather", "weight": 6.0},
    {"user_id": 2, "topic_id": "work-career", "weight": 9.0},
    {"user_id": 2, "topic_id": "meetings", "weight": 7.5},
]

# Тестовая память
MEMORIES_DATA = [
    {
        "user_id": 1,
        "session_id": "session_1",
        "kind": "episodic",
        "content": "User mentioned they like sunny weather",
        "metadata": {"emotion": "joy", "topic": "weather"}
    },
    {
        "user_id": 2,
        "session_id": "session_2", 
        "kind": "semantic",
        "content": "User works in IT and has meetings every Monday",
        "metadata": {"topic": "work-career", "frequency": "weekly"}
    }
]

# Тестовые планы обучения
LEARNING_PLANS_DATA = [
    {
        "user_id": 1,
        "target_level": "B2",
        "current_level": "B1",
        "topics": {
            "daily-life": {"priority": "high", "status": "in_progress"},
            "weather": {"priority": "medium", "status": "completed"}
        },
        "milestones": {
            "grammar_b2": {"target_date": "2024-03-01", "achieved": False},
            "pronunciation_improvement": {"target_date": "2024-02-15", "achieved": True}
        }
    }
]

# Тестовые события XP
XP_EVENTS_DATA = [
    {
        "user_id": 1,
        "session_id": "session_1",
        "event_type": "pronunciation_good",
        "xp_delta": 50,
        "metadata": {"score": 8.0, "improvement": True}
    },
    {
        "user_id": 1,
        "session_id": "session_1", 
        "event_type": "grammar_improvement",
        "xp_delta": 30,
        "metadata": {"score": 7.5, "rule": "past_simple"}
    }
]

# Тестовые записи эмоций
EMOTIONAL_LOGS_DATA = [
    {
        "user_id": 1,
        "session_id": "session_1",
        "emotion_code": "joy",
        "intensity": 0.8,
        "context": "User was happy about good weather"
    },
    {
        "user_id": 2,
        "session_id": "session_2",
        "emotion_code": "confidence", 
        "intensity": 0.9,
        "context": "User felt confident during work discussion"
    }
]
