import { useEffect, useState } from 'react';
import { Trash2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell } from '@/components/Phase2Shell';
import { useAuth } from '@/context/AuthContext';
import { p2 } from '@/lib/phase2Api';

const DeletionAuditPage = () => {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const r = await p2.eventDeletions(); setRows(r.deletions || []); }
      catch (e) { toast.error(e.response?.data?.detail || 'Failed to load audit log'); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <Phase2Shell
      title="Permanent Deletion Log"
      subtitle={user?.is_admin ? 'All permanently deleted events' : 'Permanently deleted events within your scope'}
      back={user?.is_admin ? '/admin/phase2' : '/admin/kj'}
      crumbs={[{ label: 'Deletion Log' }]}
    >
      {loading ? <p className="text-white/50">Loading…</p> : (
        <div data-testid="deletion-audit-list" className="space-y-3">
          {rows.length === 0 && (
            <div className="glass-card p-8 text-center border border-white/10">
              <ShieldAlert className="w-8 h-8 text-gold mx-auto mb-2" />
              <p className="text-white/50">No permanent deletions recorded yet.</p>
            </div>
          )}
          {rows.map((r) => (
            <div key={r.id} data-testid={`audit-row-${r.event_id}`}
              className="glass-card p-4 border border-white/10 flex items-start gap-3">
              <Trash2 className="w-5 h-5 text-red-400 mt-1 shrink-0" />
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-cinzel text-lg text-white">{r.event_name}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full border border-yellow-500/40 bg-yellow-500/20 text-yellow-300">
                    {r.event_status || 'ended'}
                  </span>
                </div>
                <p className="text-sm text-white/60 mt-1">
                  {r.venue_name || r.venue_id}{r.location_name ? ` · ${r.location_name}` : ''}
                </p>
                <p className="text-xs text-white/40 mt-1">
                  Deleted by <span className="text-gold">{r.actor_display_name || r.actor_user_id}</span>
                  {r.actor_role ? ` (${r.actor_role})` : ''} · {new Date(r.deleted_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Phase2Shell>
  );
};

export default DeletionAuditPage;
