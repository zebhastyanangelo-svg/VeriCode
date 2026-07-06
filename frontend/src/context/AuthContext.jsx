import { createContext, useContext, useState, useEffect } from 'react';
import { api, setToken, clearToken, getToken, isTokenExpired } from '../api';
import { identify, peopleSet, reset, register } from '../utils/analytics';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Carga inicial: si hay token en localStorage, fetcheamos /me para validar.
  // /me ahora devuelve must_change_password de BD; sin ese dato no podemos
  // decidir si el usuario puede entrar al panel.
  useEffect(() => {
    const t = getToken();
    if (t && !isTokenExpired(t)) {
      api.getMe()
        .then(setUser)
        .catch(() => clearToken())
        .finally(() => setLoading(false));
    } else {
      if (t) clearToken();
      setLoading(false);
    }
  }, []);

  const login = async (username, password) => {
    const data = await api.login(username, password);
    setToken(data.access_token);
    const me = await api.getMe();
    setUser(me);
    identify(me.id);
    peopleSet({ $name: me.username, $email: me.email });
    register({ platform: 'web' });
    return me;
  };

  const refreshMe = async () => {
    const me = await api.getMe();
    setUser(me);
    return me;
  };

  const logout = () => {
    clearToken();
    setUser(null);
    reset();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
