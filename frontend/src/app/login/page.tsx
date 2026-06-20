'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, systemApi, type DemoConfig } from '@/lib/api';
import { useAuthStore } from '@/lib/store';

export default function LoginPage() {
  const router = useRouter();
  const { setAuth, isAuthenticated, loadFromStorage } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);

  useEffect(() => {
    loadFromStorage();
    systemApi.getDemoConfig().then(setDemoConfig).catch(() => {});
  }, [loadFromStorage]);

  useEffect(() => {
    if (isAuthenticated) router.push('/dashboard');
  }, [isAuthenticated, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await authApi.login({ username, password });
      setAuth(res.user, res.access_token);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const fillDemoCredentials = (role: string) => {
    if (demoConfig?.demo_credentials[role]) {
      setUsername(demoConfig.demo_credentials[role].username);
      setPassword(demoConfig.demo_credentials[role].password);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--soft-beige)',
      padding: 20,
    }}>
      <div style={{
        width: '100%',
        maxWidth: 440,
      }}>
        {/* Logo & Title */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 16,
            background: 'var(--forest-green)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: 'var(--shadow-lg)',
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--forest-green)', margin: 0 }}>
            JeevanMarg
          </h1>
          <p style={{ color: 'var(--warm-gray)', fontSize: 14, marginTop: 4 }}>
            Self-Healing Emergency Corridor Agent
          </p>
        </div>

        {/* Login Card */}
        <div className="jm-card" style={{ padding: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 24, color: 'var(--forest-green)' }}>
            Sign In
          </h2>

          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6, color: 'var(--earth-brown)' }}>
                Username
              </label>
              <input
                className="jm-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6, color: 'var(--earth-brown)' }}>
                Password
              </label>
              <input
                className="jm-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
              />
            </div>

            {error && (
              <div style={{
                padding: '10px 14px', borderRadius: 8,
                background: '#FDE8E4', color: 'var(--trust-critical)',
                fontSize: 13, marginBottom: 16,
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              className="jm-btn jm-btn-primary"
              disabled={loading}
              style={{ width: '100%' }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Demo Credentials */}
          {demoConfig && (
            <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--light-sage)' }}>
              <p style={{ fontSize: 12, color: 'var(--warm-gray)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Demo Accounts
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                {Object.entries(demoConfig.demo_credentials).map(([role]) => (
                  <button
                    key={role}
                    onClick={() => fillDemoCredentials(role)}
                    className="jm-btn jm-btn-outline"
                    style={{ flex: 1, padding: '8px 12px', fontSize: 12, textTransform: 'capitalize' }}
                  >
                    {role}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <p style={{ textAlign: 'center', marginTop: 16, fontSize: 12, color: 'var(--warm-gray)' }}>
          AI Multi-Agent Emergency Corridor System • Powered by Google ADK
        </p>
      </div>
    </div>
  );
}
