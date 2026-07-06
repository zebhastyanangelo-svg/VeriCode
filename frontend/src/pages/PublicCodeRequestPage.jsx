import { useState, useEffect } from 'react';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import { getPlatformIconUrl, getPlatformFallbackIcon } from '../utils/platformIcons';
import { track } from '../utils/analytics';

export default function PublicCodeRequestPage() {
  const [email, setEmail] = useState('');
  const [platform, setPlatform] = useState('');
  const [platforms, setPlatforms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const toast = useToast();

  const fetchPlatforms = async () => {
    try {
      const data = await api.public.getPlatforms();
      setPlatforms(data);
    } catch (err) {
      setPlatforms([]);
    }
  };

  useEffect(() => {
    fetchPlatforms();
  }, []);

  const handleRequestCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      const response = await api.public.requestCode(email, platform);

      if (response && response.code) {
        setResult({
          code: response.code,
          email: email,
          platform_name: response.platform_name,
          platform_display_name: response.platform_display_name,
          platform_icon: response.platform_icon,
          received_at: response.received_at,
          sender: response.sender || '',
          subject: response.subject || '',
          is_read: response.is_read,
          is_delivered: true,
        });
        track('code_requested', {
          platform_name: response.platform_name || response.platform_display_name || '',
          email_account: email,
          success: true,
        });
        toast.success('Código entregado');
      } else {
        track('code_requested', {
          platform_name: platform || '',
          email_account: email,
          success: false,
        });
        toast.error('No se encontró código para esta cuenta y plataforma');
      }
    } catch (err) {
      toast.error(err.message || 'Error al buscar código');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="public-request-page">
      <div className="dark-bg-grid" aria-hidden="true" />
      <div className="dark-bg-glow" aria-hidden="true" />

      <nav className="dark-nav" role="navigation" aria-label="Navegación">
        <div className="dark-nav-inner">
          <a href="#/" className="dark-logo" aria-label="VeriCode inicio">
            <span className="dark-logo-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </span>
            VeriCode
          </a>
          <div className="dark-nav-links">
            <a href="#/" className="dark-btn dark-btn-ghost">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
              Volver
            </a>
            <a href="#/login" className="dark-btn-icon" aria-label="Panel de administración">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
            </a>
          </div>
        </div>
      </nav>

      <section className="request-section" aria-label="Solicitar código">
        <div className="request-card-dark">
          <div className="request-header-dark">
            <span className="bento-chip">
              <span className="chip-dot" />
              Solicitar código
            </span>
            <h1 className="request-title">Buscá tu código de verificación</h1>
            <p className="request-desc">Seleccioná tu correo y la plataforma. El código aparece al instante.</p>
          </div>

          <form onSubmit={handleRequestCode} className="request-form-dark">
            <div className="dark-form-group">
              <label htmlFor="email">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                Correo electrónico
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="ejemplo@correo.com"
                required
                className="dark-input"
              />
            </div>

            <div className="dark-form-group">
              <label htmlFor="platform">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg>
                Plataforma
              </label>
              <select
                id="platform"
                value={platform}
                onChange={e => setPlatform(e.target.value)}
                required
                className="dark-input"
              >
                <option value="">Seleccionar plataforma...</option>
                {platforms.map(p => (
                  <option key={p.id} value={p.name}>
                    {p.display_name || p.name}
                  </option>
                ))}
                {platforms.length === 0 && (
                  <option value="" disabled>No hay plataformas configuradas</option>
                )}
              </select>
            </div>

            <button
              type="submit"
              className="dark-btn dark-btn-primary dark-btn-lg btn-block"
              disabled={loading || !email || platforms.length === 0}
            >
              {loading ? (
                <>
                  <span className="btn-spinner" />
                  Buscando código...
                </>
              ) : (
                <>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                  Buscar Código
                </>
              )}
            </button>
          </form>

          {result && (
            <div className="request-result">
              <div className="result-divider" />
              <div className="live-header" style={{ marginBottom: 16 }}>
                <span className="live-indicator" />
                <span className="live-label">Código encontrado</span>
              </div>
              <div className="live-platform" style={{ marginBottom: 16 }}>
                {(() => {
                  const iconUrl = result.platform_icon ? getPlatformIconUrl(result.platform_icon) : null;
                  return iconUrl ? (
                    <img src={iconUrl} alt={result.platform_display_name || result.platform_name} className="live-icon" onError={(e) => { e.target.style.display = 'none'; }} />
                  ) : (
                    <div className="live-icon-fallback">
                      <i className={`fas ${getPlatformFallbackIcon(result.platform_icon)}`} />
                    </div>
                  );
                })()}
                <div>
                  <div className="live-name">{result.platform_display_name || result.platform_name || 'N/A'}</div>
                  <div className="live-email">{result.email || 'N/A'}</div>
                </div>
                <span className="live-badge">{result.is_read ? 'Leído' : 'Nuevo'}</span>
              </div>
              <div className="live-divider" />
              <div className="live-code-section">
                <span className="live-code-label">Código de verificación</span>
                <div className="live-code-value">{result.code}</div>
                <div className="live-code-status">
                  <span className="live-status-dot" />
                  {result.is_delivered ? 'Código listo para usar' : 'Pendiente de entrega'}
                </div>
              </div>
              <div className="live-divider" />
              <div className="result-meta">
                {result.received_at && (
                  <div className="result-meta-item">
                    <span className="result-meta-label">Recibido</span>
                    <span className="result-meta-value">{new Date(result.received_at).toLocaleString()}</span>
                  </div>
                )}
                {result.sender && (
                  <div className="result-meta-item">
                    <span className="result-meta-label">De</span>
                    <span className="result-meta-value">{result.sender}</span>
                  </div>
                )}
                {result.subject && (
                  <div className="result-meta-item">
                    <span className="result-meta-label">Asunto</span>
                    <span className="result-meta-value">{result.subject}</span>
                  </div>
                )}
              </div>
              <button
                className="dark-btn dark-btn-ghost dark-btn-lg btn-block"
                onClick={() => setResult(null)}
                style={{ marginTop: 20 }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
                Solicitar otro código
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}