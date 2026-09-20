import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Scene3D from './components/3d/Scene3D';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ReportsPage from './pages/ReportsPage';
import AgentsPage from './pages/AgentsPage';
import SettingsPage from './pages/SettingsPage';

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
        color: 'var(--text-secondary)',
        gap: 14,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: '0.85rem',
        letterSpacing: '0.08em',
        flexDirection: 'column',
      }}>
        <div style={{
          width: 44,
          height: 44,
          border: '2px solid rgba(56,189,248,0.2)',
          borderTop: '2px solid var(--accent-cyan)',
          borderRadius: '50%',
          animation: 'spin 0.7s linear infinite',
        }} />
        INITIALIZING DEEP RESEARCH PLATFORM…
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
    <ThemeProvider>
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
            <Route
              path="/reports"
              element={<ProtectedRoute><ReportsPage /></ProtectedRoute>}
            />
            <Route
              path="/agents"
              element={<ProtectedRoute><AgentsPage /></ProtectedRoute>}
            />
            <Route
              path="/settings"
              element={<ProtectedRoute><SettingsPage /></ProtectedRoute>}
            />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
