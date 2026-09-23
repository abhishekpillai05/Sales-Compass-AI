import React, { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Eye, EyeOff, Compass, UserPlus } from 'lucide-react';
import { authApi } from '@/api/auth';
import { getErrorMessage } from '@/contexts/AuthContext';
import { Spinner } from '@/components/common/Spinner';

export function RegisterPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (form.username.trim().length < 3)
      errors.username = 'Username must be at least 3 characters.';
    if (!form.email.includes('@'))
      errors.email = 'Enter a valid email address.';
    if (form.password.length < 6)
      errors.password = 'Password must be at least 6 characters.';
    if (form.password !== form.confirmPassword)
      errors.confirmPassword = 'Passwords do not match.';
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!validate()) return;
    setIsSubmitting(true);
    try {
      await authApi.register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        role: 'user',
      });
      navigate('/login', { state: { registered: true } });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm(p => ({ ...p, [key]: e.target.value }));
      if (fieldErrors[key]) setFieldErrors(p => ({ ...p, [key]: '' }));
    },
  });

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">
            <Compass size={24} color="white" />
          </div>
          <div className="auth-logo-text">
            SalesCompass AI
            <span>Product Intelligence Platform</span>
          </div>
        </div>

        <h1 className="auth-title">Create account</h1>
        <p className="auth-subtitle">Get started with SalesCompass AI</p>

        {error && (
          <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
            {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {[
            { id: 'reg-username', label: 'Username', key: 'username', type: 'text', autoComplete: 'username' },
            { id: 'reg-email', label: 'Email', key: 'email', type: 'email', autoComplete: 'email' },
          ].map(({ id, label, key, type, autoComplete }) => (
            <div key={key} className="input-wrapper">
              <label className="input-label" htmlFor={id}>{label}</label>
              <input
                id={id}
                className={`input${fieldErrors[key] ? ' input-error' : ''}`}
                type={type}
                autoComplete={autoComplete}
                {...field(key as keyof typeof form)}
                disabled={isSubmitting}
              />
              {fieldErrors[key] && (
                <span className="input-error-msg">{fieldErrors[key]}</span>
              )}
            </div>
          ))}

          <div className="input-wrapper">
            <label className="input-label" htmlFor="reg-password">Password</label>
            <div style={{ position: 'relative' }}>
              <input
                id="reg-password"
                className={`input${fieldErrors.password ? ' input-error' : ''}`}
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                style={{ paddingRight: 44 }}
                {...field('password')}
                disabled={isSubmitting}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
                style={{
                  position: 'absolute', right: 12, top: '50%',
                  transform: 'translateY(-50%)', background: 'none',
                  border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)',
                  display: 'flex', alignItems: 'center',
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {fieldErrors.password && (
              <span className="input-error-msg">{fieldErrors.password}</span>
            )}
          </div>

          <div className="input-wrapper">
            <label className="input-label" htmlFor="reg-confirm-password">Confirm Password</label>
            <input
              id="reg-confirm-password"
              className={`input${fieldErrors.confirmPassword ? ' input-error' : ''}`}
              type="password"
              autoComplete="new-password"
              {...field('confirmPassword')}
              disabled={isSubmitting}
            />
            {fieldErrors.confirmPassword && (
              <span className="input-error-msg">{fieldErrors.confirmPassword}</span>
            )}
          </div>

          <button
            id="register-submit"
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={isSubmitting}
            style={{ width: '100%', marginTop: 4 }}
          >
            {isSubmitting ? <><Spinner size={18} /> Creating account…</> : <><UserPlus size={18} /> Create account</>}
          </button>
        </form>

        <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--color-border)', textAlign: 'center', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--color-brand-600)', fontWeight: 600 }}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
