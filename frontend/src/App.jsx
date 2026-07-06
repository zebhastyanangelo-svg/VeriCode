import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { api } from './api';
import { track } from './utils/analytics';
import Navbar from './components/Navbar';
import Loading from './components/Loading';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import ChangePasswordPage from './pages/ChangePasswordPage';
import Dashboard from './pages/Dashboard';
import AccountsPage from './pages/AccountsPage';
import PlatformsPage from './pages/PlatformsPage';
import PublicCodeRequestPage from './pages/PublicCodeRequestPage';


function resolvePage(hash) {
  const route = hash.split('?')[0];
  switch (route) {
    case '/code-request': return PublicCodeRequestPage;
    case '/login': return LoginPage;
    case '/accounts': return 'admin:AccountsPage';
    case '/platforms': return 'admin:PlatformsPage';
    default: return route === '/' ? LandingPage : 'admin:Dashboard';
  }
}

function AppContent() {
  const { user, loading, logout } = useAuth();
  const [hash, setHash] = useState(window.location.hash.slice(1) || '/');

  useEffect(() => {
    const onHashChange = () => {
      const h = window.location.hash.slice(1) || '/';
      setHash(h);
      track('page_viewed', { page: h });
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const ping = () => { api.ping().catch(() => {}); };
    ping();
    const id = setInterval(ping, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <Loading text="Cargando..." />;

  // ── Pantalla bloqueante: cambio de password obligatorio ───────────────────
  // Si el usuario está autenticado y debe cambiar la contraseña, NO permitimos
  // acceso a ninguna ruta (ni admin, ni login, ni tablero, ni /code-request).
  // Esta pantalla es full-screen sin Navbar para que no haya forma de skipearla.
  if (user && user.must_change_password) {
    return <ChangePasswordPage />;
  }

  // ── Ruta pública ABSOLUTA: #/code-request ──────────────────────────────
  // Renderizar ANTES del admin guard. Es el corazón del producto: un cliente
  // sin sesión activa debe poder pedir su código de verificación acá.
  // Esta página solo consume endpoints /api/v1/public/* que NO requieren
  // JWT, así que renderizarla no expone ninguna superficie admin.
  // Se toleran query strings (igual que `resolvePage`).
  const requestRoute = hash.split('?')[0];
  if (requestRoute === '/code-request') {
    return <PublicCodeRequestPage />;
  }

  const Page = resolvePage(hash);
  if (typeof Page === 'string' && Page.startsWith('admin:')) {
    // Rutas protegidas del admin
    if (!user) return <LoginPage onLoginSuccess={() => window.location.hash = '/dashboard'} />;
    const AdminPage = Page === 'admin:Dashboard' ? Dashboard
      : Page === 'admin:AccountsPage' ? AccountsPage
      : PlatformsPage;
    return (
      <div className="app-layout">
        <Navbar user={user} onLogout={logout} />
        <main className="main-content">
          <AdminPage key={hash} />
        </main>
      </div>
    );
  }

  // Rutas públicas
  if (Page === LoginPage) return <Page onLoginSuccess={() => window.location.hash = '/dashboard'} />;
  return <Page />;
}

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ToastProvider>
  );
}

export default App;