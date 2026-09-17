import { useNavigate } from 'react-router-dom';
import { Crown, ChevronLeft, LogOut } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { roleLabel } from '@/lib/phase2Api';

export const Phase2Shell = ({ title, subtitle, crumbs = [], back, actions, children }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-royal-bg text-white/90" data-testid="phase2-admin-shell">
      <header className="border-b border-gold/20 bg-black/30 backdrop-blur sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Crown className="w-7 h-7 text-gold" />
            <div>
              <div className="font-cinzel font-bold text-lg text-gold leading-none">Phase 2 Admin</div>
              <div className="text-xs text-white/50">{roleLabel(user?.role)} · {user?.display_name}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {user?.is_admin ? (
              <button onClick={() => navigate('/admin')} data-testid="phase2-exit-btn"
                className="text-sm text-white/70 hover:text-gold transition-colors px-3 py-1.5 rounded-lg">
                Phase 1 Admin
              </button>
            ) : (
              <>
                <button onClick={() => navigate('/admin/kj')} data-testid="phase2-kj-console-btn"
                  className="text-sm text-white/70 hover:text-gold transition-colors px-3 py-1.5 rounded-lg">
                  KJ Console
                </button>
                <button onClick={() => navigate('/admin/phase2')} data-testid="phase2-locations-btn"
                  className="text-sm text-white/70 hover:text-gold transition-colors px-3 py-1.5 rounded-lg">
                  Venues
                </button>
              </>
            )}
            <button onClick={() => { logout(); navigate('/admin/login'); }} data-testid="phase2-logout-btn"
              className="text-sm text-white/70 hover:text-gold flex items-center gap-1 px-3 py-1.5 rounded-lg">
              <LogOut className="w-4 h-4" /> Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 py-8">
        {crumbs.length > 0 && (
          <nav className="text-sm text-white/50 mb-3 flex flex-wrap items-center gap-1" data-testid="phase2-breadcrumbs">
            {crumbs.map((c, i) => (
              <span key={i} className="flex items-center gap-1">
                {c.to ? (
                  <button className="hover:text-gold" onClick={() => navigate(c.to)}>{c.label}</button>
                ) : (
                  <span className="text-gold">{c.label}</span>
                )}
                {i < crumbs.length - 1 && <span className="text-white/30">/</span>}
              </span>
            ))}
          </nav>
        )}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            {back && (
              <button onClick={() => navigate(back)} data-testid="phase2-back-btn"
                className="text-white/60 hover:text-gold flex items-center gap-1 mb-2 text-sm">
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
            )}
            <h1 className="font-cinzel text-3xl font-bold text-white">{title}</h1>
            {subtitle && <p className="text-white/50 mt-1">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">{actions}</div>
        </div>
        {children}
      </main>
    </div>
  );
};

export const StatusBadge = ({ status }) => {
  const map = {
    active: 'bg-green-500/20 text-green-300 border-green-500/40',
    scheduled: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
    draft: 'bg-gray-500/20 text-gray-300 border-gray-500/40',
    ended: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
    cancelled: 'bg-red-500/20 text-red-300 border-red-500/40',
    archived: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${map[status] || map.draft}`}>{status}</span>
  );
};
