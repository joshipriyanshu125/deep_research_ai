import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Brain } from 'lucide-react';
import { login } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import TiltCard from '../components/ui/TiltCard';

export default function LoginPage() {
  const navigate = useNavigate();
  const { loginUser } = useAuth();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) =>
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.email || !form.password) { setError('Please fill in all fields.'); return; }
    setLoading(true);
    try {
      const { data } = await login({ email: form.email, password: form.password });
      loginUser(
        data.user || { email: form.email },
        data.accessToken || data.token,
        data.refreshToken
      );
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.message || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-root">
      <div className="auth-glow blue" />
      <div className="auth-glow purple" />

      <TiltCard intensity={8}>
        <div className="holo-card auth-card">
          <div className="auth-logo">
            <div className="auth-logo-icon"><Brain size={22} /></div>
            <div className="auth-logo-text">
              <h2>Deep Research AI</h2>
              <span>// AUTONOMOUS AGENT PLATFORM</span>
            </div>
          </div>

          <h1 className="auth-heading">ACCESS SYSTEM</h1>
          <p className="auth-subheading">Authenticate to continue your research sessions.</p>

          {error && <div className="auth-error-box" style={{ marginBottom: 16 }}>⚠ {error}</div>}

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <div className="form-field">
              <label className="form-label" htmlFor="login-email">// EMAIL ADDRESS</label>
              <input id="login-email" name="email" type="email" className="form-input"
                placeholder="operator@deep-research.ai" value={form.email}
                onChange={handleChange} autoComplete="email" required />
            </div>
            <div className="form-field">
              <label className="form-label" htmlFor="login-password">// ACCESS KEY</label>
              <input id="login-password" name="password" type="password" className="form-input"
                placeholder="••••••••" value={form.password}
                onChange={handleChange} autoComplete="current-password" required />
            </div>
            <button id="login-submit-btn" type="submit" className="btn-primary auth-submit" disabled={loading}>
              {loading
                ? <><span className="spinner" style={{ width: 16, height: 16 }} /> AUTHENTICATING…</>
                : '▶ INITIATE SESSION'}
            </button>
          </form>

          <p className="auth-divider">
            No account?{' '}
            <Link to="/register" className="auth-link">REQUEST ACCESS →</Link>
          </p>
        </div>
      </TiltCard>
    </div>
  );
}
