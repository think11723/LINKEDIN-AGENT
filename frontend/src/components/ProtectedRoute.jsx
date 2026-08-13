import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import { Spinner } from './ui/Feedback.jsx';

export function ProtectedRoute({ children }) {
  const { status, firebaseEnabled } = useAuth();
  const location = useLocation();

  if (firebaseEnabled === false) {
    return <Navigate to="/login" state={{ reason: 'unconfigured' }} replace />;
  }

  if (status === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center text-zinc-400">
        <Spinner className="mr-2" /> Loading…
      </div>
    );
  }

  if (status !== 'authenticated') {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}