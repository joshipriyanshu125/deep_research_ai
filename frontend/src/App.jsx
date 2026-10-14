import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ResearchProvider } from './context/ResearchContext';
import Scene3D from './components/3d/Scene3D';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ReportsPage from './pages/ReportsPage';
import AgentsPage from './pages/AgentsPage';
import SettingsPage from './pages/SettingsPage';

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background: 'var(--bg-main)',
        color: 'var(--text-primary)',
        fontFamily: 'JetBrains Mono, monospace',
        textAlign: 'center',
      }}>
        <div className="holo-card" style={{ maxWidth: 620, padding: 28 }}>
          <h1 style={{ color: 'var(--accent-red)', marginBottom: 12 }}>RENDERING ERROR</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
            The research screen could not be rendered. Your session is still safe.
            Reload the page to try again.
          </p>
          <button className="btn-primary" type="button" onClick={() => window.location.reload()}>
            RELOAD PLATFORM
          </button>
        </div>
      </div>
    );
  }
}

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
  const { user } = useAuth();

  // Keep public auth pages usable while a stored session is being restored.
  // A restored user still takes the existing authenticated redirect path.
  return user ? <Navigate to="/dashboard" replace /> : children;
}

export default function App() {
  return (
    <AppErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          {/* Global 3D background — renders on all pages */}
          <Scene3D />

          <BrowserRouter>
            <ResearchProvider>
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
            </ResearchProvider>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </AppErrorBoundary>
  );
}
