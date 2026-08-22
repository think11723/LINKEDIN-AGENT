import { useCallback, useEffect, useState } from 'react';
import { Newspaper, CheckCircle2, ExternalLink } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';
import { formatDateTime } from '../utils/date.js';

export default function PublishedPostsPage() {
  const api = useApi();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getPublishedDrafts();
      setItems(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Publishing"
        title="Published Posts"
        subtitle="Content that has already been published to LinkedIn."
      />

      <ErrorBanner error={error} onRetry={load} />

      {loading && !items.length ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : items.length ? (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={item.draft_id}>
              <CardContent className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-base font-semibold tracking-tight text-white">
                      {item.title || 'Untitled post'}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-text-muted">
                      LinkedIn Post ID: {item.linkedin_post_id ?? 'Unavailable'}
                    </div>
                  </div>
                  <Badge tone="success" size="sm" withDot>
                    <CheckCircle2 className="h-3 w-3" /> Published
                  </Badge>
                </div>

                {item.content ? (
                  <LinkedInPreview
                    authorName="You"
                    authorHeadline="on LinkedIn"
                    content={item.content}
                    hashtags={item.hashtags || []}
                  />
                ) : null}

                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <Newspaper className="h-3.5 w-3.5" />
                  Published {formatDateTime(item.published_at)}
                  {item.linkedin_post_id ? (
                    <a
                      className="ml-auto inline-flex items-center gap-1 text-brand-300 hover:underline"
                      href={`https://www.linkedin.com/feed/update/${item.linkedin_post_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open on LinkedIn <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={<Newspaper className="h-5 w-5" />}
              title="No published posts yet"
              description="Once a draft is approved and published, it will show up here."
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
