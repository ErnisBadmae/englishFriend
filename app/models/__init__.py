# Package exports for SQLAlchemy models.

from app.models.enums_and_dimensions import *
from app.models.core_tables import *
from app.models.extended_tables import *
from app.models.ml_technical import *

try:
    from app.models.prompt_models import *
    _HAS_PROMPT_MODELS = True
except ModuleNotFoundError:
    _HAS_PROMPT_MODELS = False

__all__ = [
    'CEFRLevel', 'MemoryKind', 'AccessChannel',
    'DimEmotion', 'DimTopic', 'DimAccent', 'DimLearningGoal',
    'User', 'UserChannelIdentity', 'Session', 'Utterance', 'Feedback', 'Correction',
    'UserInterest', 'Memory', 'LearningPlan', 'XPEvent',
    'MlTechnicalSession', 'MlTechnicalSessionItem', 'MlTechnicalAttempt', 'MlTechnicalExternalReview',
    'MlQuestionRevision', 'MlQuestionReview', 'MlProgressReview',
]

if _HAS_PROMPT_MODELS:
    __all__.extend([
        'PromptTemplate', 'ABExperiment', 'SessionPromptLog',
    ])
