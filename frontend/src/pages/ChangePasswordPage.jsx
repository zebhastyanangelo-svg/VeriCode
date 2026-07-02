import { useState } from 'react';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function ChangePasswordPage() {
  const { refreshMe, logout } = useAuth();
  const toast = useToast();
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword.length < 8) {
      setError('La nueva contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('La confirmación no coincide con la nueva contraseña.');
      return;
    }
    if (oldPassword === newPassword) {
      setError('La nueva contraseña debe ser distinta de la actual.');
      return;
    }

    setSubmitting(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      await refreshMe();
      toast.success('Contraseña actualizada');
    } catch (err) {
      const msg = err.message || 'No se pudo cambiar la contraseña';
      setError(msg);
      if (msg.toLowerCase().includes('sesión') || msg.toLowerCase().includes('token')) {
        logout();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="change-password-page">
      <div className="dark-bg-grid" aria-hidden="true" />
      <div className="dark-bg-glow" aria-hidden="true" />
      <div className="change-password-card-dark">
        <div className="change-password-header-dark">
          <span className="dark-logo" style={{ justifyContent: 'center', marginBottom: 12 }}>
            <span className="dark-logo-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </span>
            VeriCode
          </span>
          <span className="bento-chip" style={{ margin: '0 auto' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
            Cambio requerido
          </span>
          <h2 className="change-password-title">Actualizá tu contraseña</h2>
          <p className="change-password-desc">
            Por seguridad, debés actualizar tu contraseña antes de acceder al sistema.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="change-password-form-dark">
          <div className="dark-form-group">
            <label htmlFor="old_password">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
              Contraseña actual
            </label>
            <input
              id="old_password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
              autoFocus
              disabled={submitting}
              className="dark-input"
            />
          </div>

          <div className="dark-form-group">
            <label htmlFor="new_password">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
              Nueva contraseña
            </label>
            <input
              id="new_password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
              disabled={submitting}
              placeholder="Mínimo 8 caracteres"
              className="dark-input"
            />
          </div>

          <div className="dark-form-group">
            <label htmlFor="confirm_password">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              Confirmar nueva contraseña
            </label>
            <input
              id="confirm_password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={8}
              required
              disabled={submitting}
              className="dark-input"
            />
          </div>

          {error && (
            <div className="form-error" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="dark-btn dark-btn-primary dark-btn-lg btn-block"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="btn-spinner" />
                Actualizando...
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                Actualizar contraseña
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}