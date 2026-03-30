import { useEffect, useState } from 'react';
import { getDueVocabulary, reviewVocabularyCard, type VocabularyCard } from '../lib/api';

interface ReviewPageProps {
  userId: number;
  onReviewed: () => void;
}

const ratingButtons = [
  { label: 'Again', value: 1 },
  { label: 'Hard', value: 2 },
  { label: 'Good', value: 3 },
  { label: 'Easy', value: 4 },
];

export function ReviewPage({ userId, onReviewed }: ReviewPageProps) {
  const [cards, setCards] = useState<VocabularyCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadCards() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getDueVocabulary(userId, 12);
        if (!cancelled) {
          setCards(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load review queue');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadCards();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  async function handleReview(rating: number) {
    const currentCard = cards[0];
    if (!currentCard || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await reviewVocabularyCard(userId, {
        card_id: currentCard.id,
        rating,
      });
      setCards((prev) => prev.slice(1));
      onReviewed();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit review');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="miniapp-page center-page">
        <p>Loading review queue...</p>
      </div>
    );
  }

  const currentCard = cards[0];

  return (
    <div className="miniapp-page">
      <section className="content-card">
        <div className="section-label">Review queue</div>
        <h1>{cards.length} cards due</h1>
        <p>Rate recall honestly. The queue will reschedule itself through FSRS.</p>
      </section>

      {error && <div className="inline-error">{error}</div>}

      {currentCard ? (
        <section className="review-card">
          <div className="review-front">
            <span className="review-word">{currentCard.word}</span>
            {currentCard.translation && <span className="review-translation">{currentCard.translation}</span>}
            <p className="review-example">
              {currentCard.example_sentence || 'Use this word naturally in a work or interview context.'}
            </p>
          </div>
          <div className="review-actions">
            {ratingButtons.map((button) => (
              <button
                key={button.value}
                className="rating-button"
                disabled={isSubmitting}
                onClick={() => void handleReview(button.value)}
              >
                {button.label}
              </button>
            ))}
          </div>
        </section>
      ) : (
        <section className="content-card">
          <h2>Queue cleared</h2>
          <p>No vocabulary cards are due right now. Start a session to generate new evidence and context.</p>
        </section>
      )}

      {cards.length > 1 && (
        <section className="content-card">
          <div className="section-label">Up next</div>
          <div className="list-stack">
            {cards.slice(1, 4).map((card) => (
              <div key={card.id} className="list-item split">
                <strong>{card.word}</strong>
                {card.translation && <span className="muted-line">{card.translation}</span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
