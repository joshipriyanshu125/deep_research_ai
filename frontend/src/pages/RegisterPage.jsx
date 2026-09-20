import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Brain } from 'lucide-react';
import { register } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import TiltCard from '../components/ui/TiltCard';

function FormField({ id, name, type = 'text', label, placeholder, autoComplete, value, error, onChange }) {
  return (
    <div className="form-field">
      <label className="form-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        name={name}
        type={type}
        className={`form-input ${error ? 'error' : ''}`}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
      />
      {error && <span className="field-error">⚠ {error}</span>}
    </div>
  );
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { loginUser } = useAuth();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const validate = () => {
    const errs = {};
    if (!form.name.trim()) errs.name = 'Operator designation required.';
    if (!form.email) errs.email = 'Email address required.';
    if (!form.password || form.password.length < 8) errs.password = 'Min. 8 characters required.';
    if (form.password !== form.confirmPassword) errs.confirmPassword = 'Keys do not match.';
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setLoading(true);
    try {
      const { data } = await register({ name: form.name, email: form.email, password: form.password });
      loginUser(
        data.user || { name: form.name, email: form.email },
        data.accessToken || data.token,
        data.refreshToken
      );
      navigate('/dashboard');
    } catch (err) {
      setServerError(err.response?.data?.message || 'Registration failed. Please try again.');
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

          <h1 className="auth-heading">CREATE AGENT</h1>
          <p className="auth-subheading">Register your operator profile to begin research missions.</p>

          {serverError && <div className="auth-error-box" style={{ marginBottom: 16 }}>⚠ {serverError}</div>}

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <FormField
              id="reg-name"
              name="name"
              label="// OPERATOR DESIGNATION"
              placeholder="Full Name"
              autoComplete="name"
              value={form.name}
              error={errors.name}
              onChange={handleChange}
            />
            <FormField
              id="reg-email"
              name="email"
              type="email"
              label="// EMAIL ADDRESS"
              placeholder="operator@deep-research.ai"
              autoComplete="email"
              value={form.email}
              error={errors.email}
              onChange={handleChange}
            />
            <FormField
              id="reg-password"
              name="password"
              type="password"
              label="// ACCESS KEY"
              placeholder="Min. 8 characters"
              autoComplete="new-password"
              value={form.password}
              error={errors.password}
              onChange={handleChange}
            />
            <FormField
              id="reg-confirm"
              name="confirmPassword"
              type="password"
              label="// CONFIRM ACCESS KEY"
              placeholder="••••••••"
              autoComplete="new-password"
              value={form.confirmPassword}
              error={errors.confirmPassword}
              onChange={handleChange}
            />

            <button id="register-submit-btn" type="submit" className="btn-primary auth-submit" disabled={loading}>
              {loading
                ? <><span className="spinner" style={{ width: 16, height: 16 }} /> REGISTERING…</>
                : '▶ CREATE OPERATOR PROFILE'}
            </button>
          </form>

          <p className="auth-divider">
            Already registered?{' '}
            <Link to="/login" className="auth-link">SIGN IN →</Link>
          </p>
        </div>
      </TiltCard>
    </div>
  );
}
