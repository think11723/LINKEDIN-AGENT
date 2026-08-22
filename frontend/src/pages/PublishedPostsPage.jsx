import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Newspaper, CheckCircle2, ExternalLink, Inbox } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
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
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <Newspaper className="h-3 w-3 text-emerald-300" />
          Publishing
        </div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          <span className="text-text-secondary">Published </span>
          <span className="gradient-text">posts</span>
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {loading && items.length === 0
            ? 'Loading…'
            : `${items.length} post${items.length === 1 ? '' : 's'} live on LinkedIn.`}
        </p>
      </header>

      <ErrorBanner error={error} onRetry={load} />

      {loading && items.length === 0 ? (
        <div className="space-y-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : items.length ? (
        <ul className="space-y-3">
          {items.map((item, idx) => (
            <motion.li
              key={item.draft_id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.22 }}
            >
              <Card>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
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
            </motion.li>
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={<Inbox className="h-5 w-5" />}
          title="No published posts yet"
          description="Once a draft is approved and published, it will show up here."
        />
      )}
    </MotionPage>
  );
}
