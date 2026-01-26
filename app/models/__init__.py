# Пакет для моделей данных

# Импортируем модели в правильном порядке для избежания циклических зависимостей
from app.models.enums_and_dimensions import *
from app.models.core_tables import *
from app.models.extended_tables import *
from app.models.prompt_models import *

# Экспортируем все модели для удобства импорта
__all__ = [
    # Enums
    'CEFRLevel', 'MemoryKind', 'AccessChannel', 'ABExperimentStatus',

    # Dimensions
    'DimEmotion', 'DimTopic', 'DimAccent', 'DimLearningGoal',

    # Core tables
    'User', 'UserChannelIdentity', 'Session', 'Utterance', 'Feedback', 'Correction',

    # Extended tables
    'UserInterest', 'Memory', 'LearningPlan', 'XPEvent',

    # Prompt & A/B testing tables
    'PromptTemplate', 'ABExperiment', 'SessionPromptLog',
]
