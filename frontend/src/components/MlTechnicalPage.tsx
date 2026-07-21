import { useEffect, useState } from 'react';
import {
  getMlTechnicalTopics,
  startMlTechnicalSession,
  submitMlTechnicalAnswer,
  type MlTechnicalAnswerResponse,
  type MlTechnicalSessionQuestion,
  type MlTechnicalTopic,
  type MlTechnicalTopicProgress,
  type MlTechnicalTrackProgress,
} from '../lib/api';

interface MlTechnicalPageProps {
  userId: number;
  onBack: () => void;
}

type ViewState =
  | { mode: 'topics' }
  | { mode: 'session'; topicId: string; sessionId: string; question: MlTechnicalSessionQuestion }
  | { mode: 'reviewed'; topicId: string; sessionId: string; answeredQuestion: MlTechnicalSessionQuestion; result: MlTechnicalAnswerResponse };

function topicProgressFor(progress: MlTechnicalTrackProgress | null, topicId: string): MlTechnicalTopicProgress | undefined {
  return progress?.topics.find((topic) => topic.topic_id === topicId);
}

function difficultyLabel(difficulty: string): string {
  const labels: Record<string, string> = {
    easy: 'Базовый вопрос',
    medium: 'Средний вопрос',
    hard: 'Сложный вопрос',
  };
  return labels[difficulty] ?? 'Вопрос';
}

export function MlTechnicalPage({ userId, onBack }: MlTechnicalPageProps) {
  const [topics, setTopics] = useState<MlTechnicalTopic[]>([]);
  const [progress, setProgress] = useState<MlTechnicalTrackProgress | null>(null);
  const [view, setView] = useState<ViewState>({ mode: 'topics' });
  const [answerText, setAnswerText] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadTopics() {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await getMlTechnicalTopics(userId);
      setTopics(payload.topics);
      setProgress(payload.progress);
    } catch {
      setError('Не удалось загрузить темы ML-тренировки. Попробуйте еще раз.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadTopics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function handleStartTopic(topicId: string) {
    setError(null);
    try {
      const session = await startMlTechnicalSession(userId, topicId);
      if (!session.questions.length) {
        setError('В этой теме пока нет доступных вопросов.');
        return;
      }
      setAnswerText('');
      setView({
        mode: 'session',
        topicId,
        sessionId: session.session_id,
        question: session.questions[0],
      });
    } catch {
      setError('Не удалось начать тренировку по теме. Попробуйте еще раз.');
    }
  }

  async function submitAnswer(answer: string, answerKind: 'normal' | 'dont_know') {
    const trimmedAnswer = answer.trim();
    if (view.mode !== 'session' || (answerKind === 'normal' && !trimmedAnswer)) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await submitMlTechnicalAnswer(userId, {
        session_id: view.sessionId,
        question_id: view.question.id,
        answer_text: answerKind === 'normal' ? trimmedAnswer : '',
        answer_kind: answerKind,
        source_channel: 'web',
      });
      setView({
        mode: 'reviewed',
        topicId: view.topicId,
        sessionId: view.sessionId,
        answeredQuestion: view.question,
        result,
      });
      await loadTopics();
    } catch {
      setError('Не удалось отправить ответ. Попробуйте еще раз.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmitAnswer() {
    await submitAnswer(answerText, 'normal');
  }

  async function handleSubmitNoAnswer() {
    await submitAnswer('', 'dont_know');
  }

  function handleNextQuestion() {
    if (view.mode !== 'reviewed') return;
    if (view.result.next_question) {
      setAnswerText('');
      setView({
        mode: 'session',
        topicId: view.topicId,
        sessionId: view.sessionId,
        question: view.result.next_question,
      });
    } else {
      setView({ mode: 'topics' });
    }
  }

  if (isLoading) {
    return (
      <div className="miniapp-page center-page">
        <p>Загружаем темы ML-тренировки...</p>
      </div>
    );
  }

  return (
    <div className="miniapp-page">
      <section className="content-card">
        <div className="section-row">
          <div>
            <div className="section-label">ML и DL</div>
            <h1>Тренировка ML-собеседований</h1>
          </div>
          <button className="link-action" onClick={onBack}>
            Назад
          </button>
        </div>
        <p>
          Выберите тему, ответьте своими словами, затем разберите недостающие пункты
          и эталонное объяснение.
        </p>
        {progress && (
          <p>
            Готовность {progress.readiness_percent}%. Пройдено {progress.attempted} из {progress.total_questions} вопросов.
            Зачтено: {progress.passed}.{' '}
            {progress.needs_review > 0 && `Ждут проверки: ${progress.needs_review}. `}
            {progress.due_for_repetition > 0 && `Пора повторить: ${progress.due_for_repetition}.`}
          </p>
        )}
      </section>

      {error && <div className="inline-error">{error}</div>}

      {view.mode === 'topics' && (
        <section className="content-card">
          <div className="section-label">Темы</div>
          <div className="list-stack">
            {topics.map((topic) => {
              const topicProgress = topicProgressFor(progress, topic.id);
              const hasQuestions = (topicProgress?.total_questions ?? 0) > 0;
              return (
                <article key={topic.id} className="list-item">
                  <div className="section-row">
                    <div>
                      <strong>{topic.title_ru}</strong>
                      <span className="muted-line">{topic.description_ru}</span>
                    </div>
                    {topicProgress && (
                      <span className="tiny-pill">
                        {topicProgress.attempted}/{topicProgress.total_questions}
                      </span>
                    )}
                  </div>
                  {topicProgress && topicProgress.due_for_repetition > 0 && (
                    <p className="muted-line">Пора повторить: {topicProgress.due_for_repetition}</p>
                  )}
                  <button
                    className="primary-action"
                    disabled={!hasQuestions}
                    onClick={() => void handleStartTopic(topic.id)}
                  >
                    {hasQuestions ? 'Начать тему' : 'Скоро'}
                  </button>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {view.mode === 'session' && (
        <section className="content-card">
          <div className="section-label">{difficultyLabel(view.question.difficulty)}</div>
          <h3>{view.question.question_ru}</h3>
          <textarea
            className="answer-textarea"
            rows={8}
            value={answerText}
            onChange={(event) => setAnswerText(event.target.value)}
            placeholder="Напишите ответ своими словами на русском..."
          />
          <div className="hero-actions">
            <button
              className="primary-action"
              disabled={isSubmitting || !answerText.trim()}
              onClick={() => void handleSubmitAnswer()}
            >
              {isSubmitting ? 'Отправляем...' : 'Отправить ответ'}
            </button>
            <button
              className="link-action"
              disabled={isSubmitting}
              onClick={() => void handleSubmitNoAnswer()}
            >
              Не знаю - показать разбор
            </button>
          </div>
        </section>
      )}

      {view.mode === 'reviewed' && (
        <section className="content-card">
          <div className="section-label">{view.answeredQuestion.question_ru}</div>
          {view.result.review.status === 'needs_review' ? (
            <p>
              Ответ сохранен. Сейчас автоматический разбор недоступен, поэтому вернитесь к этому вопросу позже.
            </p>
          ) : (
            <>
              <h3>Оценка: {view.result.review.score_percent}%</h3>
              <p>{view.result.review.feedback}</p>
              {view.result.review.missing_points_text.length > 0 && (
                <>
                  <div className="section-label">Чего не хватило</div>
                  <ul>
                    {view.result.review.missing_points_text.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </>
              )}
              {view.result.review.incorrect_claims.length > 0 && (
                <>
                  <div className="section-label">Неточности</div>
                  <ul>
                    {view.result.review.incorrect_claims.map((claim) => (
                      <li key={claim}>{claim}</li>
                    ))}
                  </ul>
                </>
              )}
              {view.result.review.follow_up_question && (
                <>
                  <div className="section-label">Уточняющий вопрос интервьюера</div>
                  <p>{view.result.review.follow_up_question}</p>
                </>
              )}
            </>
          )}
          <div className="section-label">Эталонное объяснение</div>
          <p>{view.result.reference_explanation_ru}</p>
          <button className="primary-action" onClick={handleNextQuestion}>
            {view.result.next_question ? 'Следующий вопрос' : 'Вернуться к темам'}
          </button>
        </section>
      )}
    </div>
  );
}
