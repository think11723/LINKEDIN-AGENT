import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  signInWithPopup,
} from 'firebase/auth';

import { auth, firebaseEnabled, firebaseConfigError } from '../services/firebase.js';

const AuthContext = createContext(null);

const initialUser = null;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(initialUser);
  const [status, setStatus] = useState(firebaseEnabled ? 'loading' : 'unconfigured');
  const [error, setError] = useState(firebaseConfigError);

  useEffect(() => {
    if (!auth) {
      setStatus('unconfigured');
      return undefined;
    }

    // Test/debug helper: expose the Firebase auth instance on window so
    // Playwright (and DevTools) can mint ID tokens for authenticated users
    // without scraping React state. Never exposes anything sensitive.
    if (typeof window !== 'undefined') {
      window.__firebaseAuth = auth;
    }

    const unsubscribe = onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
      setStatus(nextUser ? 'authenticated' : 'unauthenticated');
      setError(null);
    });

    return () => unsubscribe();
  }, []);

  const signIn = useCallback(async (email, password) => {
    if (!auth) {
      throw new Error('Firebase auth is not configured.');
    }
    setStatus('loading');
    setError(null);
    try {
      const credential = await signInWithEmailAndPassword(auth, email, password);
      return credential.user;
    } catch (err) {
      // P0-7: a failed sign-in must leave the user clearly unauthenticated
      // so ProtectedRoute does not briefly treat them as authenticated.
      setStatus('unauthenticated');
      setError(err?.message ?? 'Sign-in failed.');
      throw err;
    }
  }, []);

  const signUp = useCallback(async (email, password) => {
    if (!auth) {
      throw new Error('Firebase auth is not configured.');
    }
    setStatus('loading');
    setError(null);
    try {
      const credential = await createUserWithEmailAndPassword(auth, email, password);
      return credential.user;
    } catch (err) {
      setStatus('unauthenticated');
      setError(err?.message ?? 'Sign-up failed.');
      throw err;
    }
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!auth) {
      throw new Error('Firebase auth is not configured.');
    }
    const provider = new GoogleAuthProvider();
    const credential = await signInWithPopup(auth, provider);
    return credential.user;
  }, []);

  const signOut = useCallback(async () => {
    if (!auth) return;
    await firebaseSignOut(auth);
  }, []);

  const value = useMemo(
    () => ({
      user,
      status,
      error,
      firebaseEnabled,
      signIn,
      signUp,
      signInWithGoogle,
      signOut,
    }),
    [user, status, error, signIn, signUp, signInWithGoogle, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return ctx;
}