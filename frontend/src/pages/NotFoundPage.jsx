import { Link } from 'react-router-dom';
import { ArrowLeft, Search } from 'lucide-react';

import { Button } from '../components/ui/Button.jsx';
import { EmptyState } from '../components/ui/Feedback.jsx';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4 animate-fadeIn">
      <div className="max-w-md text-center">
        <div className="mb-4 inline-flex items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-brand-300">
          <Search className="h-8 w-8" />
        </div>
        <div className="text-6xl font-semibold tracking-tight text-white">404</div>
        <p className="mt-3 text-base text-text-secondary">
          We couldn't find that page. It may have been moved or never existed.
        </p>
        <Link to="/dashboard" className="mt-6 inline-flex">
          <Button variant="brand" leftIcon={<ArrowLeft className="h-4 w-4" />}>
            Back to dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
