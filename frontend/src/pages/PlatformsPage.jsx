import { useState, useEffect } from 'react';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import Loading from '../components/Loading';

const COMMON_PLATFORMS = {
  netflix: {
    display_name: 'Netflix',
    provider_type: 'streaming',
    icon: 'netflix',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(netflix\\.com|account\\.netflix\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  disney_plus: {
    display_name: 'Disney+',
    provider_type: 'streaming',
    icon: 'disney',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(disneyplus\\.com|disney\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  hbo_max: {
    display_name: 'HBO Max',
    provider_type: 'streaming',
    icon: 'hbo',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(hbomax\\.com|hbo\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  prime_video: {
    display_name: 'Prime Video',
    provider_type: 'streaming',
    icon: 'prime',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(primevideo\\.com|amazon\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|otp|verification)',
  },
  spotify: {
    display_name: 'Spotify',
    provider_type: 'streaming',
    icon: 'spotify',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(spotify\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  paramount: {
    display_name: 'Paramount+',
    provider_type: 'streaming',
    icon: 'paramount',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(paramountplus\\.com|paramount\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  crunchyroll: {
    display_name: 'Crunchyroll',
    provider_type: 'streaming',
    icon: 'crunchyroll',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(crunchyroll\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  chatgpt: {
    display_name: 'ChatGPT',
    provider_type: 'ai',
    icon: 'openai',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(openai\\.com|chatgpt\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification|login)',
  },
  claude: {
    display_name: 'Claude AI',
    provider_type: 'ai',
    icon: 'anthropic',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(anthropic\\.com|claude\\.ai)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  midjourney: {
    display_name: 'Midjourney',
    provider_type: 'ai',
    icon: 'midjourney',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(midjourney\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification)',
  },
  google: {
    display_name: 'Google',
    provider_type: 'google',
    icon: 'google',
    code_pattern: '\\b(\\d{6})\\b',
    sender_pattern: '@(google\\.com|accounts\\.google\\.com)',
    subject_pattern: '(c[oó]digo|verificaci[oó]n|verification|otp)',
  },
};

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: '',
    display_name: '',
    provider_type: 'streaming',
    code_pattern: '',
    sender_pattern: '',
    subject_pattern: '',
    icon: '',
  });
  const toast = useToast();

  const fetchPlatforms = async () => {
    try {
      const data = await api.getPlatforms();
      setPlatforms(data);
    } catch (err) {
      if (!err._auth) toast.error('Error al cargar plataformas');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlatforms();
  }, []);

  const handleNameChange = (name) => {
    const common = COMMON_PLATFORMS[name.toLowerCase().trim()];
    if (common && !editing) {
      setForm((prev) => ({
        ...prev,
        name,
        display_name: common.display_name,
        provider_type: common.provider_type,
        icon: common.icon,
        code_pattern: common.code_pattern,
        sender_pattern: common.sender_pattern,
        subject_pattern: common.subject_pattern,
      }));
    } else {
      setForm((prev) => ({ ...prev, name }));
    }
  };

  const resetForm = () => {
    setForm({ name: '', display_name: '', provider_type: 'streaming', code_pattern: '', sender_pattern: '', subject_pattern: '', icon: '' });
    setEditing(null);
    setShowForm(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      if (editing) {
        const updateData = { ...form };
        if (!updateData.code_pattern) delete updateData.code_pattern;
        if (!updateData.sender_pattern) delete updateData.sender_pattern;
        if (!updateData.subject_pattern) delete updateData.subject_pattern;
        await api.updatePlatform(editing.id, updateData);
        toast.success('Plataforma actualizada');
      } else {
        await api.createPlatform(form);
        toast.success('Plataforma creada');
      }
      resetForm();
      fetchPlatforms();
    } catch (err) {
      if (!err._auth) toast.error(err.message || 'Error al guardar la plataforma');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (platform) => {
    setForm({
      name: platform.name,
      display_name: platform.display_name || '',
      provider_type: platform.provider_type,
      code_pattern: platform.code_pattern || '',
      sender_pattern: platform.sender_pattern || '',
      subject_pattern: platform.subject_pattern || '',
      icon: platform.icon || '',
    });
    setEditing(platform);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar esta plataforma?')) return;
    try {
      await api.deletePlatform(id);
      toast.success('Plataforma eliminada');
      fetchPlatforms();
    } catch (err) {
      if (!err._auth) toast.error(err.message);
    }
  };

  if (loading) return <Loading text="Cargando plataformas..." />;

  return (
    <div className="page">
      <div className="page-header">
        <h1><i className="fas fa-tv" aria-hidden="true"></i> Plataformas</h1>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true); }}>
          <i className="fas fa-plus" aria-hidden="true"></i> Agregar Plataforma
        </button>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={(e) => e.target.className === 'modal-overlay' && resetForm()}>
          <div className="modal">
            <div className="modal-header">
              <h2>{editing ? 'Editar Plataforma' : 'Nueva Plataforma'}</h2>
              <button className="btn-close" onClick={resetForm}>&times;</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-row">
                <div className="form-group flex-1">
                  <label>Nombre (ID)</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => handleNameChange(e.target.value)}
                    required
                    placeholder="netflix"
                    disabled={!!editing}
                    list="common-platforms"
                  />
                  <datalist id="common-platforms">
                    {Object.keys(COMMON_PLATFORMS).map((key) => (
                      <option key={key} value={key} />
                    ))}
                  </datalist>
                </div>
                <div className="form-group flex-1">
                  <label>Nombre mostrado</label>
                  <input
                    type="text"
                    value={form.display_name}
                    onChange={e => setForm({ ...form, display_name: e.target.value })}
                    placeholder="Netflix"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Tipo</label>
                  <select value={form.provider_type} onChange={e => setForm({ ...form, provider_type: e.target.value })}>
                    <option value="streaming">Streaming</option>
                    <option value="ai">IA</option>
                    <option value="google">Google</option>
                    <option value="other">Otro</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Icono</label>
                  <input
                    type="text"
                    value={form.icon}
                    onChange={e => setForm({ ...form, icon: e.target.value })}
                    placeholder="netflix"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Patrón de código (regex)</label>
                <input
                  type="text"
                  value={form.code_pattern}
                  onChange={e => setForm({ ...form, code_pattern: e.target.value })}
                  placeholder={'\\b(\\d{6})\\b'}
                />
              </div>

              <div className="form-group">
                <label>Patrón de remitente (regex)</label>
                <input
                  type="text"
                  value={form.sender_pattern}
                  onChange={e => setForm({ ...form, sender_pattern: e.target.value })}
                  placeholder="info@netflix.com"
                />
              </div>

              <div className="form-group">
                <label>Patrón de asunto (regex)</label>
                <input
                  type="text"
                  value={form.subject_pattern}
                  onChange={e => setForm({ ...form, subject_pattern: e.target.value })}
                  placeholder="código|verificación"
                />
              </div>

              <div className="form-actions">
                <button type="button" className="btn btn-outline" onClick={resetForm}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Guardando...' : editing ? 'Guardar Cambios' : 'Crear Plataforma'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Plataforma</th>
              <th>Tipo</th>
              <th>Patrón código</th>
              <th>Patrón remitente</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {platforms.map(p => (
              <tr key={p.id}>
                <td>
                  <strong>{p.display_name || p.name}</strong>
                  <div className="text-muted">{p.name}</div>
                </td>
                <td>
                  <span className={`badge badge-${p.provider_type}`}>
                    {p.provider_type === 'streaming' ? '📺 Streaming' : p.provider_type === 'ai' ? '🤖 IA' : p.provider_type === 'google' ? '🔵 Google' : '📦 Otro'}
                  </span>
                </td>
                <td><code className="code-inline">{p.code_pattern || '-'}</code></td>
                <td><code className="code-inline">{p.sender_pattern || '-'}</code></td>
                <td>
                  <span className={`status-dot ${p.is_active ? 'active' : 'inactive'}`}></span>
                  {p.is_active ? 'Activo' : 'Inactivo'}
                </td>
                <td className="actions-cell">
                  <button className="btn btn-sm" onClick={() => handleEdit(p)} aria-label="Editar" title="Editar">
                    <i className="fas fa-edit" aria-hidden="true"></i>
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(p.id)} aria-label="Eliminar" title="Eliminar">
                    <i className="fas fa-trash" aria-hidden="true"></i>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
