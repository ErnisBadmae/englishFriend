# Пакет для моделей данных

# Импортируем модели в правильном порядке для избежания циклических зависимостей
from app.models.enums_and_dimensions import *
from app.models.core_tables import *
from app.models.extended_tables import *

# Экспортируем все модели для удобства импорта
__all__ = [
    # Enums
    'CEFRLevel', 'MemoryKind', 'AccessChannel',
    
    # Dimensions
    'DimEmotion', 'DimTopic', 'DimAccent',
    
    # Core tables
    'User', 'UserChannelIdentity', 'Session', 'Utterance', 'Feedback', 'Correction',
    
    # Extended tables
    'UserInterest', 'Memory', 'LearningPlan', 'XPEvent',
]
