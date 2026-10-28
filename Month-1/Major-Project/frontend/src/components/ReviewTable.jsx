import { useMemo } from 'react';
import { format } from 'date-fns';

export default function ReviewTable({ reviews, loading = false }) {
  const columns = useMemo(() => [
    { key: 'review_text', header: 'Review', width: '40%' },
    { key: 'rating', header: 'Rating', width: '10%' },
    { key: 'sentiment', header: 'Sentiment', width: '15%' },
    { key: 'sentiment_score', header: 'Score', width: '10%' },
    { key: 'review_date', header: 'Date', width: '15%' },
    { key: 'reviewer', header: 'Reviewer', width: '10%' },
  ], []);

  if (loading) {
    return (
      <div className="table-container">
        <table>
          <thead>
            <tr>
              {columns.map((col) => <th key={col.key} style={{ width: col.width }}>{col.header}</th>)}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i}>
                <td><div className="skeleton" style={{ height: '1rem', width: '80%' }} /></td>
                <td><div className="skeleton" style={{ height: '1rem', width: '3rem' }} /></td>
                <td><div className="skeleton badge" style={{ height: '1.5rem', width: '6rem' }} /></td>
                <td><div className="skeleton" style={{ height: '1rem', width: '4rem' }} /></td>
                <td><div className="skeleton" style={{ height: '1rem', width: '7rem' }} /></td>
                <td><div className="skeleton" style={{ height: '1rem', width: '6rem' }} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (!reviews || reviews.length === 0) {
    return (
      <div className="empty-state">
        <p>No reviews found</p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            {columns.map((col) => <th key={col.key} style={{ width: col.width }}>{col.header}</th>)}
          </tr>
        </thead>
        <tbody>
          {reviews.map((review) => (
            <tr key={review.id || review._id}>
              <td className="review-text">
                <div className="review-text-content">
                  {review.review_text || review.cleaned_text}
                </div>
              </td>
              <td>
                <span className="rating-stars">
                  {'★'.repeat(review.rating || 0)}{'☆'.repeat(5 - (review.rating || 0))}
                </span>
              </td>
              <td>
                <span className={`badge badge-${review.sentiment}`}>
                  {review.sentiment}
                </span>
              </td>
              <td>
                <span className="sentiment-score">
                  {(review.sentiment_score || 0).toFixed(2)}
                </span>
              </td>
              <td>
                {review.review_date ? format(new Date(review.review_date), 'MMM d, yyyy') : '-'}
              </td>
              <td>{review.reviewer || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}