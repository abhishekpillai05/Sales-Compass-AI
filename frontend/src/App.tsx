import React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
} from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AppLayout } from '@/components/layout/AppLayout';
import { FullPageSpinner } from '@/components/common/Spinner';

import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { ChatPage } from '@/pages/ChatPage';
import { SearchPage } from '@/pages/SearchPage';
import { UploadPage } from '@/pages/UploadPage';
import { AdminPage } from '@/pages/AdminPage';
import { ManagementPage } from '@/pages/ManagementPage';

/**
 * Protects routes that require authentication.
 * Redirects unauthenticated users to /login.
 * Shows a full-page spinner while the session check is in progress.
 */
function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <FullPageSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
}

/**
 * Routes that are accessible without authentication.
 * Redirects already-authenticated users to /chat.
 */
function PublicRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <FullPageSpinner />;
  if (isAuthenticated) return <Navigate to="/chat" replace />;

  return <Outlet />;
}

/**
 * Protects admin-only routes (/upload, /admin).
 * Redirects non-admin users (e.g. Salesman) to /chat.
 */
function AdminRoute() {
  const { isAdmin, isLoading } = useAuth();

  if (isLoading) return <FullPageSpinner />;
  if (!isAdmin) return <Navigate to="/chat" replace />;

  return <Outlet />;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<PublicRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Protected routes (All authenticated users: ADMIN & SALESMAN) */}
      <Route element={<ProtectedRoute />}>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/search" element={<SearchPage />} />

        {/* Admin-only routes */}
        <Route element={<AdminRoute />}>
          <Route path="/admin/users" element={<ManagementPage />} />
          <Route path="/management" element={<Navigate to="/admin/users" replace />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Route>
      </Route>

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
