import { Routes, Route, Navigate } from 'react-router-dom';

import { AppShell } from './layouts/AppShell.jsx';
import { ProtectedRoute } from './components/ProtectedRoute.jsx';

import LoginPage from './pages/LoginPage.jsx';
import SignupPage from './pages/SignupPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import CreatePostPage from './pages/CreatePostPage.jsx';
import DraftsPage from './pages/DraftsPage.jsx';
import DraftViewerPage from './pages/DraftViewerPage.jsx';
import ResumeStudioPage from './pages/ResumeStudioPage.jsx';
import ResumeEditorPage from './pages/ResumeEditorPage.jsx';
import ResumeATSPage from './pages/ResumeATSPage.jsx';
import ResumeLinkedInPage from './pages/ResumeLinkedInPage.jsx';
import ApprovalPage from './pages/ApprovalPage.jsx';
import ApprovalFromEmailPage from './pages/ApprovalFromEmailPage.jsx';
import ScheduledPostsPage from './pages/ScheduledPostsPage.jsx';
import PublishedPostsPage from './pages/PublishedPostsPage.jsx';
import ProfilePage from './pages/ProfilePage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/create" element={<CreatePostPage />} />
        <Route path="/drafts" element={<DraftsPage />} />
        <Route path="/drafts/:id" element={<DraftViewerPage />} />
        <Route path="/resume" element={<ResumeStudioPage />} />
        <Route path="/resume/new" element={<ResumeEditorPage />} />
        <Route path="/resume/:id" element={<ResumeEditorPage />} />
        <Route path="/resume/:id/edit" element={<ResumeEditorPage />} />
        <Route path="/resume/:id/ats" element={<ResumeATSPage />} />
        <Route path="/resume/:id/linkedin" element={<ResumeLinkedInPage />} />
        <Route path="/approval" element={<ApprovalPage />} />
        <Route path="/approve" element={<ApprovalFromEmailPage />} />
        <Route path="/scheduled-posts" element={<ScheduledPostsPage />} />
        <Route path="/published-posts" element={<PublishedPostsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}