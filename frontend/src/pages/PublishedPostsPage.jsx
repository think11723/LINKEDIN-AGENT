import { useCallback, useEffect, useState } from 'react';
import { Newspaper } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { Skeleton, EmptyState, ErrorBanner } from '../components/ui/Feedback.jsx';
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
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Published Posts</h1>
        <p className="text-zinc-400">Content that has already been published to LinkedIn.</p>
      </div>

      <ErrorBanner error={error} onRetry={load} />

      <Card>
        <CardHeader>
          <CardTitle>Recent publishes</CardTitle>
          <CardDescription>{items.length} post(s) published.</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : items.length ? (
            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.draft_id} className="panel-muted p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-zinc-100">{item.title || 'Untitled'}</div>
                      <div className="mt-1 text-sm text-zinc-400">
                        LinkedIn Post ID: {item.linkedin_post_id ?? 'Unavailable'}
                      </div>
                    </div>
                    <Badge variant="success">Published</Badge>
                  </div>
                  {item.content ? (
                    <div className="mt-3 max-h-32 overflow-auto whitespace-pre-line rounded-lg border border-white/5 bg-black/30 p-3 text-sm text-zinc-300">
                      {item.content}
                    </div>
                  ) : null}
                  <div className="mt-2 flex items-center gap-2 text-xs text-zinc-500">
                    <Newspaper className="h-3.5 w-3.5" />
                    Published {formatDateTime(item.published_at)}
                  </div>
                  {item.hashtags?.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.hashtags.map((tag) => (
                        <Badge key={tag}>{tag}</Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No published posts yet"
              description="Once a draft is approved and published, it will show up here."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}