import React, { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Eye, EyeOff, Compass, LogIn } from 'lucide-react';
import { useAuth, getErrorMessage } from '@/contexts/AuthContext';
import { Spinner } from '@/components/common/Spinner';

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{
    username?: string;
    password?: string;
  }>({});

  // Already logged in — redirect immediately
  React.useEffect(() => {
    if (isAuthenticated) navigate('/chat', { replace: true });
  }, [isAuthenticated, navigate]);

  function validate(): boolean {
    const errors: typeof fieldErrors = {};
    if (!username.trim()) errors.username = 'Username is required.';
    if (!password) errors.password = 'Password is required.';
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate('/chat', { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* Logo */}
        <div className="auth-logo">
          <div className="auth-logo-icon">
            <Compass size={24} color="white" />
          </div>
          <div className="auth-logo-text">
            SalesCompass AI
            <span>Product Intelligence Platform</span>
          </div>
        </div>

        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-subtitle">Sign in to your account to continue</p>

        {/* Error */}
        {error && (
          <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
            {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Username */}
          <div className="input-wrapper">
            <label className="input-label" htmlFor="login-username">
              Username
            </label>
            <input
              id="login-username"
              className={`input${fieldErrors.username ? ' input-error' : ''}`}
              type="text"
              autoComplete="username"
              placeholder="Enter your username"
              value={username}
              onChange={e => {
                setUsername(e.target.value);
                if (fieldErrors.username)
                  setFieldErrors(p => ({ ...p, username: undefined }));
              }}
              disabled={isSubmitting}
              aria-describedby={fieldErrors.username ? 'username-error' : undefined}
            />
            {fieldErrors.username && (
              <span id="username-error" className="input-error-msg">
                {fieldErrors.username}
              </span>
            )}
          </div>

          {/* Password */}
          <div className="input-wrapper">
            <label className="input-label" htmlFor="login-password">
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="login-password"
                className={`input${fieldErrors.password ? ' input-error' : ''}`}
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={e => {
                  setPassword(e.target.value);
                  if (fieldErrors.password)
                    setFieldErrors(p => ({ ...p, password: undefined }));
                }}
                disabled={isSubmitting}
                style={{ paddingRight: 44 }}
                aria-describedby={fieldErrors.password ? 'password-error' : undefined}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute',
                  right: 12,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {fieldErrors.password && (
              <span id="password-error" className="input-error-msg">
                {fieldErrors.password}
              </span>
            )}
          </div>

          <button
            id="login-submit"
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={isSubmitting}
            style={{ width: '100%', marginTop: 4 }}
          >
            {isSubmitting ? (
              <>
                <Spinner size={18} />
                Signing in…
              </>
            ) : (
              <>
                <LogIn size={18} />
                Sign in
              </>
            )}
          </button>
        </form>

        <div
          style={{
            marginTop: 24,
            paddingTop: 20,
            borderTop: '1px solid var(--color-border)',
            textAlign: 'center',
            fontSize: '0.8125rem',
            color: 'var(--color-text-muted)',
          }}
        >
          Don't have an account?{' '}
          <Link to="/register" style={{ color: 'var(--color-brand-600)', fontWeight: 600 }}>
            Register
          </Link>
        </div>
      </div>
    </div>
  );
}
