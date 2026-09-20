import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Scene3D from './components/3d/Scene3D';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-main)',
        color: 'var(--text-muted)',
        gap: 12,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: '0.8rem',
        letterSpacing: '0.08em',
        flexDirection: 'column',
      }}>
        <div style={{
          width: 40,
          height: 40,
          border: '2px solid rgba(56,189,248,0.15)',
          borderTop: '2px solid #38BDF8',
          borderRadius: '50%',
          animation: 'spin 0.7s linear infinite',
        }} />
        INITIALIZING SYSTEM…
      </div>
    );
  }

  return user ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  return !user ? children : <Navigate to="/dashboard" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      {/* Global 3D background — renders on all pages */}
      <Scene3D />

      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/login"
            element={<PublicRoute><LoginPage /></PublicRoute>}
          />
          <Route
            path="/register"
            element={<PublicRoute><RegisterPage /></PublicRoute>}
          />
          <Route
            path="/dashboard"
            element={<ProtectedRoute><DashboardPage /></ProtectedRoute>}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
