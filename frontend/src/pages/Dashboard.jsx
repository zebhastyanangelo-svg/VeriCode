import { useState, useEffect, useRef } from 'react';
import { api, getToken } from '../api';
import { useToast } from '../context/ToastContext';
import CodeCard from '../components/CodeCard';
import Loading from '../components/Loading';

export default function Dashboard() {
  const [codes, setCodes] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const toast = useToast();
  const wsRef = useRef(null);
  const reconnectAttempt = useRef(0);
  const requestSeqRef = useRef(0);

  const fetchData = async (query = '') => {
    const seq = ++requestSeqRef.current;
    try {
      const [codesData, statsData] = await Promise.all([
        api.getCodes({ q: query || undefined, limit: 50 }),
        api.getCodeStats(),
      ]);
      // Solo aplicamos si la respuesta corresponde al último request.
      if (seq !== requestSeqRef.current) return;
      setCodes(codesData);
      setStats(statsData);
    } catch (err) {
      if (seq !== requestSeqRef.current) return;
      if (!err._auth) toast.error('Error al cargar datos');
    } finally {
      if (seq === requestSeqRef.current) {
        setLoading(false);
      }
    }
  };

  // Fetch inicial sin debounce cuando el componente monta.
  useEffect(() => {
    setLoading(true);
    fetchData('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Búsqueda server-side con debounce cuando el filtro cambia.
  useEffect(() => {
    if (!filter) return; // El mount ya hace el fetch inicial
    setLoading(true);
    const timer = setTimeout(() => {
      fetchData(filter);
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  useEffect(() => {
    if (!getToken()) return;
    let reconnectTimer = null;
    let cancelled = false;

    const connectWs = () => {
      if (cancelled) return;
      try {
        const ws = new WebSocket(api.getWsUrl());
        wsRef.current = ws;
      } catch (err) {
        scheduleReconnect();
        return;
      }

      wsRef.current.onopen = () => {
        reconnectAttempt.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'new_code') {
            setCodes(prev => {
              if (prev.some(c => c.id === msg.data.id)) return prev;
              return [msg.data, ...prev].slice(0, 200);
            });
            // Refresh stats silently
            api.getCodeStats().then(setStats).catch(() => {});
          }
        } catch (e) { /* ignore */ }
      };

      wsRef.current.onerror = () => {
        // close handler will fire next
      };

      wsRef.current.onclose = () => {
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      // Backoff exponencial: 1s, 2s, 4s, 8s, ..., cap 30s. Con ±20% jitter.
      const attempt = Math.min(reconnectAttempt.current, 6);
      const base = Math.min(30000, 1000 * Math.pow(2, attempt));
      const jitter = base * (0.2 * (Math.random() - 0.5));
      const delay = Math.max(500, Math.round(base + jitter));
      reconnectAttempt.current += 1;
      reconnectTimer = setTimeout(connectWs, delay);
    };

    connectWs();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch (e) { /* ignore */ }
      }
    };
  }, []);

  const handleMarkRead = async (id) => {
    try {
      await api.markRead(id);
      setCodes(prev => prev.map(c => c.id === id ? { ...c, is_read: true } : c));
    } catch (err) {
      toast.error('Error al marcar como leído');
    }
  };

  const handleDeliver = async (id, deliveredTo) => {
    try {
      await api.markDelivered(id, deliveredTo);
      setCodes(prev => prev.map(c =>
        c.id === id ? { ...c, is_delivered: true, delivered_to: deliveredTo } : c
      ));
      toast.success(`Código entregado a ${deliveredTo}`);
      api.getCodeStats().then(setStats).catch(() => {});
    } catch (err) {
      toast.error('Error al entregar código');
    }
  };

  if (loading) return <Loading text="Cargando dashboard..." />;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1><i className="fas fa-home" aria-hidden="true"></i> Dashboard</h1>
        <div className="header-actions">
          <button className="btn btn-sm" onClick={() => { setLoading(true); fetchData(filter); }}>
            <i className="fas fa-sync-alt" aria-hidden="true"></i> Actualizar
          </button>
        </div>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card stat-total">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">Total códigos</div>
          </div>
          <div className="stat-card stat-unread">
            <div className="stat-value">{stats.unread}</div>
            <div className="stat-label">Sin leer</div>
          </div>
          <div className="stat-card stat-undelivered">
            <div className="stat-value">{stats.undelivered}</div>
            <div className="stat-label">Sin entregar</div>
          </div>
          <div className="stat-card stat-hour">
            <div className="stat-value">{stats.last_hour}</div>
            <div className="stat-label">Última hora</div>
          </div>
        </div>
      )}

      <div className="search-bar">
        <i className="fas fa-search" aria-hidden="true"></i>
        <input
          type="text"
          placeholder="Buscar por código, correo, plataforma..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
        />
        {filter && (
          <button className="btn-clear" onClick={() => setFilter('')}>
            <i className="fas fa-times" aria-hidden="true"></i>
          </button>
        )}
      </div>

      <div className="codes-grid">
        {codes.length === 0 ? (
          <div className="empty-state">
            <i className="fas fa-inbox" aria-hidden="true"></i>
            <p>{filter ? 'Sin resultados para tu búsqueda' : 'No hay códigos de verificación'}</p>
          </div>
        ) : (
          codes.map(c => (
            <CodeCard
              key={c.id}
              code={c}
              onMarkRead={handleMarkRead}
              onDeliver={handleDeliver}
            />
          ))
        )}
      </div>
    </div>
  );
}
