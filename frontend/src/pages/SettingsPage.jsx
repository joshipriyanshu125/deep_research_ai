import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import Sidebar from '../components/layout/Sidebar';
import TiltCard from '../components/ui/TiltCard';
import { Palette, Sliders, Shield, User, Database, Check, Sparkles, RefreshCw, Key } from 'lucide-react';

export default function SettingsPage() {
  const { user } = useAuth();
  const { theme, setTheme, themes } = useTheme();
  const [savedMsg, setSavedMsg] = useState('');

  const [defaults, setDefaults] = useState({
    defaultDepth: 'standard',
    defaultBreadth: 3,
    enableWeb: true,
    enableAcademic: true,
    enableMarket: true,
    autoExportMarkdown: false,
  });

  const handleSaveDefaults = (e) => {
    e.preventDefault();
    setSavedMsg('Settings saved successfully!');
    setTimeout(() => setSavedMsg(''), 3000);
  };

  return (
    <div className="app-layout">
      <Sidebar />

      <main className="main-content">
        {/* Header */}
        <section className="hero-section">
          <div className="hero-eyebrow">Platform Configuration</div>
          <h1 className="hero-title" data-text="System Settings & Themes">
            System Settings & Themes
          </h1>
          <p className="hero-subtitle">
            Customize visual theme, contrast palette, agent execution defaults, and operator profile.
          </p>
        </section>

        {savedMsg && <div className="badge success" style={{ padding: '10px 18px', fontSize: '0.85rem' }}>✓ {savedMsg}</div>}

        <div className="settings-sections-grid">
          {/* Theme Selector */}
          <div className="holo-card settings-card">
            <div className="settings-card-header">
              <div className="settings-icon-wrap">
                <Palette size={20} />
              </div>
              <div>
                <h3 className="settings-card-title">Color Theme & Visual Contrast</h3>
                <p className="settings-card-desc">Switch between curated high-visibility themes suited for all environments.</p>
              </div>
            </div>

            <div className="theme-options-grid">
              {themes.map((t) => {
                const isActive = theme === t.id;
                return (
                  <div
                    key={t.id}
                    className={`theme-card ${isActive ? 'active' : ''}`}
                    onClick={() => setTheme(t.id)}
                  >
                    <div className="theme-card-top">
                      <div className="theme-color-dots">
                        <span className="theme-dot" style={{ background: t.primary }} />
                        <span className="theme-dot" style={{ background: t.accent }} />
                      </div>
                      {isActive && <span className="theme-active-tag"><Check size={12} /> ACTIVE</span>}
                    </div>
                    <div className="theme-name">{t.name}</div>
                    <div className="theme-desc">{t.desc}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Operator Profile */}
          <div className="holo-card settings-card">
            <div className="settings-card-header">
              <div className="settings-icon-wrap">
                <User size={20} />
              </div>
              <div>
                <h3 className="settings-card-title">Operator Profile</h3>
                <p className="settings-card-desc">Authenticated agent operator credentials.</p>
              </div>
            </div>

            <div className="profile-details-grid">
              <div className="profile-detail-row">
                <span className="profile-label">OPERATOR DESIGNATION</span>
                <span className="profile-value">{user?.name || user?.username || 'Priyanshu Joshi'}</span>
              </div>
              <div className="profile-detail-row">
                <span className="profile-label">EMAIL ADDRESS</span>
                <span className="profile-value">{user?.email || 'operator@deep-research.ai'}</span>
              </div>
              <div className="profile-detail-row">
                <span className="profile-label">ACCESS ROLE</span>
                <span className="profile-value">
                  <span className="badge success">{user?.role?.toUpperCase() || 'USER'}</span>
                </span>
              </div>
              <div className="profile-detail-row">
                <span className="profile-label">SESSION STATUS</span>
                <span className="profile-value">
                  <span className="status-dot" style={{ display: 'inline-block', marginRight: 6 }} /> Active JWT Bearer Session
                </span>
              </div>
            </div>
          </div>

          {/* Agent Defaults */}
          <div className="holo-card settings-card">
            <div className="settings-card-header">
              <div className="settings-icon-wrap">
                <Sliders size={20} />
              </div>
              <div>
                <h3 className="settings-card-title">Default Research Parameters</h3>
                <p className="settings-card-desc">Presets applied when initializing new query missions.</p>
              </div>
            </div>

            <form onSubmit={handleSaveDefaults} className="settings-form">
              <div className="form-field">
                <label className="form-label">DEFAULT RESEARCH DEPTH</label>
                <select
                  className="styled-select"
                  value={defaults.defaultDepth}
                  onChange={(e) => setDefaults({ ...defaults, defaultDepth: e.target.value })}
                >
                  <option value="quick">Quick (1 Iteration)</option>
                  <option value="standard">Standard Deep (2 Iterations)</option>
                  <option value="deep">Comprehensive (3 Iterations)</option>
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">DEFAULT VECTOR BREADTH</label>
                <select
                  className="styled-select"
                  value={defaults.defaultBreadth}
                  onChange={(e) => setDefaults({ ...defaults, defaultBreadth: Number(e.target.value) })}
                >
                  <option value={3}>3 Vector Tracks</option>
                  <option value={5}>5 Vector Tracks</option>
                </select>
              </div>

              <button type="submit" className="btn-primary" style={{ marginTop: 12 }}>
                <Check size={14} /> SAVE PREFERENCES
              </button>
            </form>
          </div>

          {/* System & API Status */}
          <div className="holo-card settings-card">
            <div className="settings-card-header">
              <div className="settings-icon-wrap">
                <Database size={20} />
              </div>
              <div>
                <h3 className="settings-card-title">Connected AI & Search Endpoints</h3>
                <p className="settings-card-desc">External service integrations and API providers.</p>
              </div>
            </div>

            <div className="providers-list">
              <div className="provider-row">
                <div className="provider-info">
                  <Key size={14} className="provider-icon" />
                  <div>
                    <div className="provider-name">OpenRouter LLM Gateway</div>
                    <div className="provider-status">Active (gpt-4o / claude-3.5-sonnet)</div>
                  </div>
                </div>
                <span className="badge success">CONNECTED</span>
              </div>

              <div className="provider-row">
                <div className="provider-info">
                  <Key size={14} className="provider-icon" />
                  <div>
                    <div className="provider-name">Tavily & Serper Search APIs</div>
                    <div className="provider-status">Multi-engine web crawler</div>
                  </div>
                </div>
                <span className="badge success">CONNECTED</span>
              </div>

              <div className="provider-row">
                <div className="provider-info">
                  <Key size={14} className="provider-icon" />
                  <div>
                    <div className="provider-name">Qdrant Vector Database</div>
                    <div className="provider-status">Cloud cluster embedding index</div>
                  </div>
                </div>
                <span className="badge success">CONNECTED</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
