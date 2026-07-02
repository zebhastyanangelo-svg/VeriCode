import { useState } from 'react';

export default function CodeCard({ code, onMarkRead, onDeliver }) {
  const [deliverTo, setDeliverTo] = useState('');

  const getTimeAgo = (dateStr) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Ahora';
    if (mins < 60) return `hace ${mins}m`;
    const hours = Math.floor(mins / 60);
    return `hace ${hours}h`;
  };

  const handleDeliver = () => {
    if (deliverTo.trim()) {
      onDeliver(code.id, deliverTo.trim());
      setDeliverTo('');
    }
  };

  return (
    <div className={`code-card ${code.is_delivered ? 'delivered' : ''} ${code.is_read ? '' : 'unread'}`}>
      <div className="code-card-header">
        <span className="platform-badge" title={code.platform_name}>
          {code.platform_name || 'Desconocida'}
        </span>
        <span className="code-time">{getTimeAgo(code.received_at)}</span>
      </div>

      <div className="code-value">{code.code}</div>

      <div className="code-card-body">
        {code.email && (
          <div className="code-meta">
            <i className="fas fa-envelope"></i> {code.email}
          </div>
        )}
        {code.sender && (
          <div className="code-meta">
            <i className="fas fa-user"></i> {code.sender}
          </div>
        )}
        {code.subject && (
          <div className="code-meta code-subject">
            <i className="fas fa-tag"></i> {code.subject.length > 50 ? code.subject.slice(0, 50) + '...' : code.subject}
          </div>
        )}
      </div>

      <div className="code-card-actions">
        {!code.is_read && (
          <button className="btn btn-sm" onClick={() => onMarkRead(code.id)}>
            <i className="fas fa-check"></i> Leído
          </button>
        )}
        <div className="deliver-row">
          <input
            type="text"
            placeholder="Entregar a..."
            value={deliverTo}
            onChange={e => setDeliverTo(e.target.value)}
            className="input-sm"
          />
          <button className="btn btn-sm btn-primary" onClick={handleDeliver}>
            <i className="fas fa-paper-plane"></i>
          </button>
        </div>
      </div>
    </div>
  );
}
