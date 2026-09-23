import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { authApi } from '@/api/auth';
import { ApiClientError } from '@/api/client';
import type { UserResponse } from '@/types/api';

interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;          // true while fetching /auth/me on mount
  isAuthenticated: boolean;
  isAdmin: boolean;
  isSalesman: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  error: string | null;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // On mount: try to restore session from the httponly cookie
  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    const userData = await authApi.login({ username, password });
    setUser(userData);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Even if the request fails, clear local state
    }
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const roleUpper = user?.role?.toUpperCase();
  const isAdmin = roleUpper === 'ADMIN';
  const isSalesman = roleUpper === 'SALESMAN' || (!isAdmin && !!user);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: user !== null,
        isAdmin,
        isSalesman,
        login,
        logout,
        error,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

/** Returns a user-friendly error message from any thrown error */
export function getErrorMessage(err: unknown): string {
  if (err instanceof ApiClientError) return err.message;
  if (err instanceof Error) return err.message;
  return 'An unexpected error occurred.';
}
