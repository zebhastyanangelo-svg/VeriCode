import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import LogoSphere from '../components/LogoSphere';

const stagger = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
};

function FadeUp({ children, delay = 0, className = '' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function ScaleIn({ children, delay = 0, className = '' }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default function LandingPage() {
  const heroRef = useRef(null);
  const heroInView = useInView(heroRef, { once: true, margin: '-100px' });

  return (
    <div className="landing-dark">
      {/* Animated background grid */}
      <div className="dark-bg-grid" aria-hidden="true" />
      <div className="dark-bg-glow" aria-hidden="true" />

      {/* Nav */}
      <nav className="dark-nav" role="navigation" aria-label="Navegación principal">
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
            <a href="#/code-request" className="dark-btn dark-btn-primary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 7 4 4 20 4 20 7" /><line x1="9" y1="20" x2="15" y2="20" /><line x1="12" y1="4" x2="12" y2="20" /></svg>
              Solicitar Código
            </a>
            <a href="#/login" className="dark-btn-icon" aria-label="Panel de administración">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
            </a>
          </div>
        </div>
      </nav>

      {/* Hero — Bento Grid */}
      <section className="dark-hero" ref={heroRef} aria-label="Sección principal">
        <div className="bento-grid">
          {/* Main hero text — spans 2 cols */}
          <motion.div
            className="bento-card bento-hero"
            initial={{ opacity: 0, y: 40 }}
            animate={heroInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="bento-chip">
              <span className="chip-dot" />
              Sistema de verificación inteligente
            </span>
            <h1 className="bento-hero-title">
              Tus códigos de verificación<br />
              <span className="text-gradient">al instante</span>
            </h1>
            <p className="bento-hero-desc">
              Elegí tu correo y plataforma. Nosotros buscamos el código mientras vos
              te ocupás de lo que importa.
            </p>
            <div className="bento-hero-actions">
              <a href="#/code-request" className="dark-btn dark-btn-primary dark-btn-lg">
                Solicitar Código
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
              </a>
              <a href="#/login" className="dark-btn dark-btn-ghost dark-btn-lg">
                Panel Admin
              </a>
            </div>
          </motion.div>

          {/* Live code card */}
          <motion.div
            className="bento-card bento-live"
            initial={{ opacity: 0, scale: 0.92 }}
            animate={heroInView ? { opacity: 1, scale: 1 } : {}}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          >
            <div className="live-header">
              <span className="live-indicator" />
              <span className="live-label">En vivo</span>
            </div>
            <div className="live-platform">
              <img src="https://svgl.app/library/spotify.svg" alt="Spotify" className="live-icon" />
              <div>
                <div className="live-name">Spotify</div>
                <div className="live-email">cuenta@gmail.com</div>
              </div>
              <span className="live-badge">Nuevo</span>
            </div>
            <div className="live-divider" />
            <div className="live-code-section">
              <span className="live-code-label">Código de verificación</span>
              <div className="live-code-value">482 193</div>
              <div className="live-code-status">
                <span className="live-status-dot" />
                Código listo para usar
              </div>
            </div>
          </motion.div>

          {/* Stats card */}
          <motion.div
            className="bento-card bento-stats"
            initial={{ opacity: 0, y: 30 }}
            animate={heroInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.25 }}
          >
            <div className="stat-row">
              <div className="stat-item">
                <span className="stat-number">1,284</span>
                <span className="stat-label">Códigos extraídos</span>
              </div>
              <div className="stat-divider" />
              <div className="stat-item">
                <span className="stat-number">32</span>
                <span className="stat-label">Cuentas activas</span>
              </div>
            </div>
          </motion.div>

          {/* Mini platforms card */}
          <motion.div
            className="bento-card bento-mini-platforms"
            initial={{ opacity: 0, y: 30 }}
            animate={heroInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.35 }}
          >
            <div className="mini-platforms-grid">
              {['Netflix', 'Disney+', 'Prime Video', 'Spotify', 'HBO Max'].map(p => (
                <span key={p} className="mini-platform-chip">{p}</span>
              ))}
              <span className="mini-platform-chip mini-more">+15</span>
            </div>
            <span className="mini-platforms-label">Plataformas compatibles</span>
          </motion.div>
        </div>
      </section>

      {/* Stats Banner */}
      <FadeUp>
        <section className="dark-stats-banner" aria-label="Estadísticas">
          <div className="stat-banner-item">
            <span className="stat-banner-number">99.9%</span>
            <span className="stat-banner-label">Tasa de detección</span>
          </div>
          <div className="stat-banner-divider" />
          <div className="stat-banner-item">
            <span className="stat-banner-number">&lt;30s</span>
            <span className="stat-banner-label">Tiempo promedio</span>
          </div>
          <div className="stat-banner-divider" />
          <div className="stat-banner-item">
            <span className="stat-banner-number">20+</span>
            <span className="stat-banner-label">Plataformas</span>
          </div>
        </section>
      </FadeUp>

      {/* Features Bento */}
      <section className="dark-features" aria-label="Características">
        <FadeUp>
          <div className="section-tag">Características</div>
          <h2 className="section-title">Cómo funciona</h2>
        </FadeUp>

        <div className="features-bento">
          <FadeUp delay={0.1} className="feature-bento-card feature-card-large">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
            </div>
            <h3>Conectamos tus cuentas</h3>
            <p>Vinculamos las casillas que ya usás. El sistema las monitorea automáticamente 24/7 sin que tengas que hacer nada.</p>
          </FadeUp>

          <FadeUp delay={0.2} className="feature-bento-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
            </div>
            <h3>Detección automática</h3>
            <p>Apenas llega un correo de verificación, extraemos el código con los patrones de cada plataforma.</p>
          </FadeUp>

          <FadeUp delay={0.3} className="feature-bento-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
            </div>
            <h3>Entrega al instante</h3>
            <p>Seleccioná tu correo y plataforma. El código aparece al toque sin buscar entre miles de mensajes.</p>
          </FadeUp>

          <FadeUp delay={0.4} className="feature-bento-card feature-card-wide">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
            </div>
            <h3>Seguro y privado</h3>
            <p>Las credenciales se almacenan cifradas. Solo vos tenés acceso a los códigos de tus cuentas.</p>
          </FadeUp>
        </div>
      </section>

      {/* Platforms Sphere */}
      <section className="dark-platforms" aria-label="Plataformas compatibles">
        <FadeUp>
          <div className="section-tag">Plataformas</div>
          <h2 className="section-title">
            Compatible con <span className="text-gradient">20+ plataformas</span> premium
          </h2>
        </FadeUp>

        <ScaleIn delay={0.1}>
          <LogoSphere />
        </ScaleIn>
      </section>

      {/* CTA */}
      <section className="dark-cta" aria-label="Llamado a la acción">
        <FadeUp>
          <div className="cta-card">
            <h2 className="cta-title">Obtené tu primer código ahora</h2>
            <p className="cta-desc">Sin registro, sin esperas. Elegí tu correo y plataforma, y el código aparece al instante.</p>
            <a href="#/code-request" className="dark-btn dark-btn-primary dark-btn-lg">
              Solicitar Código
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
            </a>
          </div>
        </FadeUp>
      </section>

      {/* Footer */}
      <footer className="dark-footer" role="contentinfo">
        <div className="dark-footer-inner">
          <div className="dark-footer-main">
            <a href="#/" className="dark-logo">
              <span className="dark-logo-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </span>
              VeriCode
            </a>
            <div className="dark-footer-links">
              <a href="#/code-request">Solicitar código</a>
              <a href="#/login">Panel admin</a>
            </div>
          </div>
          <p className="dark-footer-copy">Sistema de gestión de códigos de verificación.</p>
        </div>
      </footer>
    </div>
  );
}