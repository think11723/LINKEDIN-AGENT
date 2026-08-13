import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { Button } from '../components/ui/Button.jsx';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4 text-center">
      <div className="space-y-4">
        <div className="text-6xl font-semibold text-zinc-100">404</div>
        <div className="text-xl text-zinc-300">We couldn't find that page.</div>
        <p className="text-zinc-500">It may have been moved or never existed.</p>
        <Link to="/dashboard" className="inline-flex">
          <Button>
            <ArrowLeft className="h-4 w-4" /> Back to dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}