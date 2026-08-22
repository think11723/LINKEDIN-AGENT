import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Search, Home, Inbox } from 'lucide-react';

import { Button } from '../components/ui/Button.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';

export default function NotFoundPage() {
  return (
    <MotionPage className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardContent className="space-y-6 p-8 text-center">
          <motion.div
            initial={{ scale: 0.96, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="mx-auto inline-flex h-16 w-16 items-center justify-center rounded-2xl gradient-brand shadow-glow-brand"
          >
            <Inbox className="h-7 w-7 text-white" />
          </motion.div>
          <div>
            <div className="text-5xl font-semibold tracking-tight text-white">
              404
            </div>
            <h1 className="mt-2 text-lg font-semibold text-zinc-100">
              We couldn't find that page
            </h1>
            <p className="mt-1 text-sm text-text-secondary">
              The link may be broken or the page may have been moved.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button
              variant="brand"
              leftIcon={<Home className="h-4 w-4" />}
            >
              <Link to="/dashboard">Back to dashboard</Link>
            </Button>
            <Button
              variant="secondary"
              leftIcon={<ArrowLeft className="h-4 w-4" />}
            >
              <Link to="/drafts">My drafts</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </MotionPage>
  );
}
