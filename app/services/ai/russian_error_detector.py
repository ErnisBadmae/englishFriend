"""
Детектор типичных ошибок русскоговорящих в английском.

Анализирует текст на:
1. Грамматические паттерны (артикли, предлоги)
2. Потенциальные pronunciation ошибки (W/V, TH)
3. Типичные интерференции русского языка
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ErrorCategory(Enum):
    """Категории ошибок."""
    ARTICLE = "article"           # Артикли a/an/the
    PREPOSITION = "preposition"   # Предлоги
    WORD_ORDER = "word_order"     # Порядок слов
    PRONUNCIATION = "pronunciation"  # Произношение (из текста)
    GRAMMAR = "grammar"           # Общие грамматические
    VOCABULARY = "vocabulary"     # Лексические


class ErrorSeverity(Enum):
    """Серьёзность ошибки."""
    MINOR = "minor"       # Можно игнорировать
    MODERATE = "moderate" # Стоит исправить мягко
    MAJOR = "major"       # Нужно исправить сразу


@dataclass
class DetectedError:
    """Обнаруженная ошибка."""
    category: ErrorCategory
    severity: ErrorSeverity
    original: str           # Что сказал студент
    correction: str         # Правильный вариант
    explanation: str        # Объяснение для ментора
    position: int = 0       # Позиция в тексте
    russian_hint: str = ""  # Подсказка на русском


@dataclass
class AnalysisResult:
    """Результат анализа текста."""
    text: str
    errors: list[DetectedError] = field(default_factory=list)
    pronunciation_warnings: list[str] = field(default_factory=list)
    suggested_focus: Optional[str] = None  # На чём сфокусироваться

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def major_errors(self) -> list[DetectedError]:
        return [e for e in self.errors if e.severity == ErrorSeverity.MAJOR]


# Паттерны для детекции ошибок

# 1. Отсутствующие артикли
MISSING_ARTICLE_PATTERNS = [
    # "I went to store" -> "I went to THE store"
    (r'\b(went to|go to|going to|came to|come to)\s+(store|school|hospital|bank|office|gym|park|beach|cinema|theater|restaurant|cafe|shop|market|station|airport)\b',
     r'\1 the \2',
     "Missing 'the' before specific place"),

    # "I have car" -> "I have A car"
    (r'\b(have|has|got|need|want|bought|found)\s+(car|dog|cat|house|phone|computer|book|friend|problem|question|idea)\b',
     r'\1 a \2',
     "Missing 'a' before singular countable noun"),

    # "She is doctor" -> "She is A doctor"
    (r'\b(is|am|are|was|were|become|became)\s+(doctor|teacher|engineer|student|driver|writer|actor|singer|lawyer|manager)\b',
     r'\1 a \2',
     "Missing 'a' before profession"),
]

# 2. Неправильные предлоги (интерференция из русского)
PREPOSITION_ERRORS = [
    # "depend from" -> "depend on" (зависеть от)
    (r'\bdepend(?:s|ed|ing)?\s+from\b', 'depend on', 'Russian interference: "зависеть от"'),

    # "listen music" -> "listen to music"
    (r'\blisten(?:s|ed|ing)?\s+(music|radio|podcast|song)', r'listen to \1', 'Missing "to" after "listen"'),

    # "married with" -> "married to"
    (r'\bmarried\s+with\b', 'married to', 'Russian interference: "женат на"'),

    # "consist from" -> "consist of"
    (r'\bconsist(?:s|ed|ing)?\s+from\b', 'consist of', 'Russian interference: "состоять из"'),

    # "afraid from" -> "afraid of"
    (r'\bafraid\s+from\b', 'afraid of', 'Russian interference: "бояться чего-то"'),

    # "interested of" -> "interested in"
    (r'\binterested\s+(of|for)\b', 'interested in', 'Should be "interested in"'),
]

# 3. Типичные грамматические ошибки
GRAMMAR_ERRORS = [
    # "most of people" -> "most people"
    (r'\bmost of (people|students|children|adults|users)\b', r'most \1', '"Most of" needs "the": most of THE people, or just "most people"'),

    # "informations" -> "information"
    (r'\binformations\b', 'information', 'Uncountable noun - no plural'),

    # "advices" -> "advice"
    (r'\badvices\b', 'advice', 'Uncountable noun - no plural'),

    # "furnitures" -> "furniture"
    (r'\bfurnitures\b', 'furniture', 'Uncountable noun - no plural'),

    # "I am agree" -> "I agree"
    (r'\bI am agree\b', 'I agree', 'No "am" needed with "agree"'),

    # "discuss about" -> "discuss"
    (r'\bdiscuss(?:ed|ing|es)?\s+about\b', 'discuss', '"Discuss" is transitive - no "about" needed'),

    # Double negatives
    (r"\bdon't\s+know\s+nothing\b", "don't know anything", 'Avoid double negatives'),

    # Subject-verb agreement: "He/She don't" -> "doesn't"
    (r'\b(he|she|it)\s+don\'t\b', r"\1 doesn't", 'Third person singular needs "doesn\'t"'),

    # "I am work" -> "I work" or "I am working"
    (r'\bI am (go|work|live|study|play|eat|sleep|read|write)\b', r'I \1', 'Use simple present without "am" or add "-ing"'),

    # "I am like" -> "I like"
    (r'\bI am (like|love|hate|want|need|know|think|believe)\b', r'I \1', 'Stative verbs don\'t use continuous form'),

    # "peoples" -> "people"
    (r'\bpeoples\b', 'people', '"People" is already plural'),

    # "childs" -> "children"
    (r'\bchilds\b', 'children', 'Irregular plural: child → children'),

    # "I'm new with" -> "I'm new to"
    (r"\bI'?m new (with|in)\b", "I'm new to", '"New to" is the correct preposition'),

    # "fresh with" -> incorrect (suggests alternative)
    (r'\bfresh with\b', 'new to', '"Fresh with" is not idiomatic - use "new to"'),
]

# 4. Слова с потенциальными pronunciation проблемами для русских
PRONUNCIATION_WATCH_WORDS = {
    # W/V confusion
    'w_words': ['where', 'what', 'when', 'why', 'which', 'while', 'water', 'weather',
                'winter', 'woman', 'world', 'work', 'would', 'want', 'was', 'were',
                'with', 'without', 'week', 'weekend', 'well', 'welcome', 'west'],

    # TH sounds (θ and ð)
    'th_voiceless': ['think', 'thought', 'through', 'three', 'throw', 'thank',
                     'thing', 'thick', 'thin', 'Thursday', 'thousand', 'threat'],
    'th_voiced': ['the', 'this', 'that', 'these', 'those', 'they', 'them', 'their',
                  'there', 'then', 'than', 'though', 'together', 'other', 'mother',
                  'father', 'brother', 'weather', 'whether'],

    # Short/long vowel pairs
    'vowel_pairs': {
        'ship': 'sheep', 'bit': 'beat', 'sit': 'seat', 'fit': 'feet',
        'live': 'leave', 'fill': 'feel', 'still': 'steal',
        'pull': 'pool', 'full': 'fool', 'look': 'Luke',
        'cut': 'cart', 'but': 'bart', 'hut': 'heart',
    },

    # Final consonant devoicing risk
    'final_voiced': ['bad', 'dog', 'big', 'bag', 'rib', 'robe', 'bed', 'red',
                     'good', 'food', 'made', 'said', 'lived', 'loved', 'moved'],
}


class RussianErrorDetector:
    """Детектор ошибок для русскоговорящих студентов."""

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Компилируем регулярные выражения для скорости."""
        self.article_patterns = [
            (re.compile(p, re.IGNORECASE), repl, expl)
            for p, repl, expl in MISSING_ARTICLE_PATTERNS
        ]
        self.preposition_patterns = [
            (re.compile(p, re.IGNORECASE), repl, expl)
            for p, repl, expl in PREPOSITION_ERRORS
        ]
        self.grammar_patterns = [
            (re.compile(p, re.IGNORECASE), repl, expl)
            for p, repl, expl in GRAMMAR_ERRORS
        ]

    def analyze(self, text: str) -> AnalysisResult:
        """
        Анализирует текст студента на типичные ошибки.

        Args:
            text: Текст от студента (транскрипт речи)

        Returns:
            AnalysisResult с найденными ошибками и рекомендациями
        """
        result = AnalysisResult(text=text)

        # Проверяем грамматические паттерны
        self._check_articles(text, result)
        self._check_prepositions(text, result)
        self._check_grammar(text, result)

        # Отмечаем слова для внимания к произношению
        self._check_pronunciation_words(text, result)

        # Определяем фокус для обратной связи
        self._determine_focus(result)

        return result

    def _check_articles(self, text: str, result: AnalysisResult):
        """Проверка на пропущенные артикли."""
        for pattern, replacement, explanation in self.article_patterns:
            for match in pattern.finditer(text):
                corrected = pattern.sub(replacement, match.group())
                result.errors.append(DetectedError(
                    category=ErrorCategory.ARTICLE,
                    severity=ErrorSeverity.MODERATE,
                    original=match.group(),
                    correction=corrected,
                    explanation=explanation,
                    position=match.start(),
                    russian_hint="В английском нужны артикли a/the перед существительными",
                ))

    def _check_prepositions(self, text: str, result: AnalysisResult):
        """Проверка на неправильные предлоги."""
        for pattern, replacement, explanation in self.preposition_patterns:
            for match in pattern.finditer(text):
                result.errors.append(DetectedError(
                    category=ErrorCategory.PREPOSITION,
                    severity=ErrorSeverity.MODERATE,
                    original=match.group(),
                    correction=replacement if not replacement.startswith('\\') else pattern.sub(replacement, match.group()),
                    explanation=explanation,
                    position=match.start(),
                    russian_hint="Предлоги в английском отличаются от русских",
                ))

    def _check_grammar(self, text: str, result: AnalysisResult):
        """Проверка общих грамматических ошибок."""
        for pattern, replacement, explanation in self.grammar_patterns:
            for match in pattern.finditer(text):
                corrected = pattern.sub(replacement, match.group())
                result.errors.append(DetectedError(
                    category=ErrorCategory.GRAMMAR,
                    severity=ErrorSeverity.MAJOR if 'double' in explanation.lower() else ErrorSeverity.MODERATE,
                    original=match.group(),
                    correction=corrected,
                    explanation=explanation,
                    position=match.start(),
                ))

    def _check_pronunciation_words(self, text: str, result: AnalysisResult):
        """Отмечаем слова, требующие внимания к произношению."""
        text_lower = text.lower()
        words = set(re.findall(r'\b[a-z]+\b', text_lower))

        # W/V слова
        w_words_found = words.intersection(PRONUNCIATION_WATCH_WORDS['w_words'])
        if w_words_found:
            result.pronunciation_warnings.append(
                f"W sounds: {', '.join(sorted(w_words_found)[:3])} - check lips are rounded"
            )

        # TH слова
        th_words = words.intersection(
            set(PRONUNCIATION_WATCH_WORDS['th_voiceless']) |
            set(PRONUNCIATION_WATCH_WORDS['th_voiced'])
        )
        if th_words:
            result.pronunciation_warnings.append(
                f"TH sounds: {', '.join(sorted(th_words)[:3])} - tongue between teeth"
            )

        # Final voiced consonants
        final_voiced = words.intersection(PRONUNCIATION_WATCH_WORDS['final_voiced'])
        if final_voiced:
            result.pronunciation_warnings.append(
                f"Final voiced: {', '.join(sorted(final_voiced)[:3])} - keep voice on the final sound"
            )

    def _determine_focus(self, result: AnalysisResult):
        """Определяем на чём сфокусировать обратную связь."""
        if not result.errors and not result.pronunciation_warnings:
            result.suggested_focus = None
            return

        # Приоритет: major errors > moderate errors > pronunciation
        major = result.major_errors
        if major:
            result.suggested_focus = f"Grammar: {major[0].explanation}"
            return

        if result.errors:
            # Группируем по категории
            categories = {}
            for e in result.errors:
                categories[e.category] = categories.get(e.category, 0) + 1

            most_common = max(categories, key=categories.get)
            result.suggested_focus = f"Focus on: {most_common.value}"
            return

        if result.pronunciation_warnings:
            result.suggested_focus = result.pronunciation_warnings[0]


# Singleton instance
_detector: Optional[RussianErrorDetector] = None


def get_detector() -> RussianErrorDetector:
    """Получить instance детектора."""
    global _detector
    if _detector is None:
        _detector = RussianErrorDetector()
    return _detector


def analyze_student_text(text: str) -> AnalysisResult:
    """
    Быстрый анализ текста студента.

    Args:
        text: Транскрипт речи студента

    Returns:
        AnalysisResult с ошибками и рекомендациями
    """
    return get_detector().analyze(text)


def format_errors_for_prompt(result: AnalysisResult, max_errors: int = 3) -> str:
    """
    Форматирует ошибки для добавления в промпт ментора.

    Args:
        result: Результат анализа
        max_errors: Максимум ошибок для показа

    Returns:
        Строка для добавления в промпт
    """
    if not result.has_errors and not result.pronunciation_warnings:
        return ""

    lines = ["## Detected Issues in Student's Speech"]

    # Major errors first
    for error in result.major_errors[:max_errors]:
        lines.append(f"- CORRECT THIS: '{error.original}' → '{error.correction}'")

    # Then moderate errors
    moderate = [e for e in result.errors if e.severity == ErrorSeverity.MODERATE]
    for error in moderate[:max_errors - len(result.major_errors)]:
        lines.append(f"- Gentle correction: '{error.original}' → '{error.correction}'")

    # Pronunciation notes
    if result.pronunciation_warnings:
        lines.append(f"- Pronunciation note: {result.pronunciation_warnings[0]}")

    return "\n".join(lines)
