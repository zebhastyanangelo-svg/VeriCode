import { useState, useEffect } from 'react';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import Loading from '../components/Loading';

export default function AccountsPage() {
  const [accounts, setAccounts] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    email: '',
    password: '',
    email_type: 'gmail',
    imap_host: '',
    imap_port: 993,
    notes: '',
    platform_id: '',
  });
  const toast = useToast();

  const fetchAccounts = async () => {
    try {
      const data = await api.getEmailAccounts();
      setAccounts(data);
    } catch (err) {
      toast.error('Error al cargar cuentas');
    } finally {
      setLoading(false);
    }
  };

  const fetchPlatforms = async () => {
    try {
      const data = await api.getPlatforms();
      setPlatforms(data.filter(p => p.is_active));
    } catch (err) {
      toast.error('Error al cargar plataformas');
    }
  };

  useEffect(() => {
    fetchAccounts();
    fetchPlatforms();
  }, []);

  const resetForm = () => {
    setForm({ email: '', password: '', email_type: 'gmail', imap_host: '', imap_port: 993, notes: '', platform_id: '' });
    setEditing(null);
    setShowForm(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const submitData = { ...form };
      if (submitData.platform_id === '') delete submitData.platform_id;
      if (editing) {
        const updateData = { ...submitData };
        if (!updateData.password) delete updateData.password;
        await api.updateEmailAccount(editing.id, updateData);
        toast.success('Cuenta actualizada');
      } else {
        await api.createEmailAccount(submitData);
        toast.success('Cuenta creada');
      }
      resetForm();
      fetchAccounts();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleEdit = (account) => {
    setForm({
      email: account.email,
      password: '',
      email_type: account.email_type,
      imap_host: account.imap_host || '',
      imap_port: account.imap_port || 993,
      notes: account.notes || '',
      platform_id: account.platform_id || '',
    });
    setEditing(account);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar esta cuenta?')) return;
    try {
      await api.deleteEmailAccount(id);
      toast.success('Cuenta eliminada');
      fetchAccounts();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleTest = async (id) => {
    try {
      const res = await api.testEmailConnection(id);
      toast.success(res.message);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handlePoll = async (id) => {
    try {
      const res = await api.pollEmailAccount(id);
      toast.success(res.message);
    } catch (err) {
      toast.error(err.message);
    }
  };

  if (loading) return <Loading text="Cargando cuentas..." />;

  return (
    <div className="page">
      <div className="page-header">
        <h1><i className="fas fa-envelope"></i> Cuentas de Correo</h1>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true); }}>
          <i className="fas fa-plus"></i> Agregar Cuenta
        </button>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={(e) => e.target.className === 'modal-overlay' && resetForm()}>
          <div className="modal">
            <div className="modal-header">
              <h2>{editing ? 'Editar Cuenta' : 'Nueva Cuenta'}</h2>
              <button className="btn-close" onClick={resetForm}>&times;</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-row">
                <div className="form-group flex-1">
                  <label>Correo electrónico</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={e => setForm({ ...form, email: e.target.value })}
                    required
                    placeholder="cuenta@correo.com"
                  />
                </div>
                <div className="form-group">
                  <label>Tipo</label>
                  <select value={form.email_type} onChange={e => setForm({ ...form, email_type: e.target.value })}>
                    <option value="gmail">Gmail</option>
                    <option value="outlook">Outlook</option>
                    <option value="yahoo">Yahoo</option>
                    <option value="custom">Personalizado</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Plataforma (opcional)</label>
                <select value={form.platform_id} onChange={e => setForm({ ...form, platform_id: e.target.value })}>
                  <option value="">Sin plataforma asignada (auto-detectar)</option>
                  {platforms.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.display_name || p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Contraseña</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  required={!editing}
                  placeholder={editing ? 'Dejar vacío para no cambiar' : 'Contraseña del correo'}
                />
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label>Servidor IMAP (opcional)</label>
                  <input
                    type="text"
                    value={form.imap_host}
                    onChange={e => setForm({ ...form, imap_host: e.target.value })}
                    placeholder={form.email_type === 'gmail' ? 'imap.gmail.com' : form.email_type === 'outlook' ? 'outlook.office365.com' : 'imap.example.com'}
                  />
                </div>
                <div className="form-group" style={{ width: '100px' }}>
                  <label>Puerto</label>
                  <input
                    type="number"
                    value={form.imap_port}
                    onChange={e => setForm({ ...form, imap_port: parseInt(e.target.value) || 993 })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Notas</label>
                <textarea
                  value={form.notes}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  placeholder="Información adicional..."
                  rows={2}
                />
              </div>

              <div className="form-actions">
                <button type="button" className="btn btn-outline" onClick={resetForm}>Cancelar</button>
                <button type="submit" className="btn btn-primary">
                  {editing ? 'Guardar Cambios' : 'Crear Cuenta'}
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
              <th>Correo</th>
              <th>Tipo</th>
              <th>Plataforma</th>
              <th>Estado</th>
              <th>Última verificación</th>
              <th>Notas</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map(a => (
              <tr key={a.id}>
                <td><strong>{a.email}</strong></td>
                <td><span className={`badge badge-${a.email_type}`}>{a.email_type}</span></td>
                <td className="text-muted">{a.platform_id ? (platforms.find(p => p.id === a.platform_id)?.display_name || a.platform_id) : 'Auto'}</td>
                <td>
                  <span className={`status-dot ${a.is_active ? 'active' : 'inactive'}`}></span>
                  {a.is_active ? 'Activo' : 'Inactivo'}
                </td>
                <td>{a.last_checked ? new Date(a.last_checked).toLocaleString() : 'Nunca'}</td>
                <td className="text-muted">{a.notes || '-'}</td>
                <td className="actions-cell">
                  <button className="btn btn-sm" onClick={() => handleTest(a.id)} title="Probar conexión">
                    <i className="fas fa-plug"></i>
                  </button>
                  <button className="btn btn-sm" onClick={() => handlePoll(a.id)} title="Verificar ahora">
                    <i className="fas fa-sync-alt"></i>
                  </button>
                  <button className="btn btn-sm" onClick={() => handleEdit(a)} title="Editar">
                    <i className="fas fa-edit"></i>
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(a.id)} title="Eliminar">
                    <i className="fas fa-trash"></i>
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
