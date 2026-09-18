import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, ShieldCheck, ShieldOff, UserCog, Building2, Check } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell } from '@/components/Phase2Shell';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { p2, roleLabel } from '@/lib/phase2Api';

// Dev Admin Staff Management: find a user, grant/revoke Venue KJ, activate/deactivate,
// and assign authorized venues. All enforcement is server-side; this is the control surface.
const StaffPage = () => {
  const [users, setUsers] = useState([]);
  const [locations, setLocations] = useState([]);
  const [venues, setVenues] = useState([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // user being edited
  const [form, setForm] = useState({ role: 'singer', staff_active: false, venue_ids: [] });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [us, locs, vns] = await Promise.all([p2.adminUsers(), p2.locations(), p2.venues()]);
      setUsers(us); setLocations(locs); setVenues(vns);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to load users'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return users
      .filter((u) => !u.is_admin) // never manage a global admin's staff here
      .filter((u) => !s || u.display_name?.toLowerCase().includes(s) || u.email?.toLowerCase().includes(s))
      .slice(0, 100);
  }, [users, q]);

  const venuesByLocation = useMemo(() => {
    const m = {};
    for (const v of venues) (m[v.location_id] = m[v.location_id] || []).push(v);
    return m;
  }, [venues]);
  const locName = (id) => locations.find((l) => l.id === id)?.name || 'Location';

  const openEdit = (u) => {
    setEditing(u);
    setForm({
      role: u.role === 'venue_kj' ? 'venue_kj' : 'singer',
      staff_active: !!u.staff_active,
      venue_ids: u.role_scope?.venue_ids || [],
    });
  };

  const toggleVenue = (id) => setForm((f) => ({
    ...f, venue_ids: f.venue_ids.includes(id) ? f.venue_ids.filter((x) => x !== id) : [...f.venue_ids, id],
  }));

  const save = async () => {
    if (!editing) return;
    if (form.role === 'venue_kj' && form.staff_active && form.venue_ids.length === 0) {
      toast.error('Assign at least one venue before activating a Venue KJ'); return;
    }
    setSaving(true);
    try {
      const body = form.role === 'singer'
        ? { role: 'singer', staff_active: false, venue_ids: [], location_ids: [] }
        : { role: 'venue_kj', staff_active: form.staff_active, venue_ids: form.venue_ids, location_ids: [] };
      await p2.setStaff(editing.id, body);
      toast.success('Staff authorization updated');
      setEditing(null);
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update'); }
    finally { setSaving(false); }
  };

  return (
    <Phase2Shell title="Staff Management" subtitle="Grant, revoke, and scope Venue KJ access"
      crumbs={[{ label: 'Locations', to: '/admin/phase2' }, { label: 'Staff' }]}>
      <div className="glass-card p-4 border border-white/10 mb-6" data-testid="staff-search">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
          <input data-testid="staff-search-input" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search users by name or email…" className="w-full royal-input pl-12 bg-black/40" />
        </div>
      </div>

      {loading ? <p className="text-white/50">Loading users…</p> : (
        <div className="glass-card border border-white/10 overflow-hidden" data-testid="staff-table">
          <table className="w-full text-sm">
            <thead><tr className="text-white/50 text-left border-b border-white/10">
              <th className="py-3 px-4">User</th><th className="px-4">Role</th><th className="px-4">Staff Access</th><th className="px-4">Venues</th><th className="px-4"></th>
            </tr></thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan="5" className="text-white/40 py-6 px-4">No users found.</td></tr>}
              {filtered.map((u) => (
                <tr key={u.id} className="border-b border-white/5" data-testid={`staff-row-${u.id}`}>
                  <td className="py-3 px-4"><div className="text-white">{u.display_name}</div><div className="text-white/40 text-xs">{u.email}</div></td>
                  <td className="px-4"><span className="text-white/80">{roleLabel(u.role)}</span></td>
                  <td className="px-4" data-testid={`staff-active-${u.id}`}>
                    {u.staff_active && u.role !== 'singer'
                      ? <span className="inline-flex items-center gap-1 text-green-400"><ShieldCheck className="w-4 h-4" /> Active</span>
                      : <span className="inline-flex items-center gap-1 text-white/40"><ShieldOff className="w-4 h-4" /> Inactive</span>}
                  </td>
                  <td className="px-4 text-white/60">{(u.role_scope?.venue_ids || []).length}</td>
                  <td className="px-4 text-right">
                    <button data-testid={`staff-manage-${u.id}`} onClick={() => openEdit(u)}
                      className="inline-flex items-center gap-1 text-gold hover:brightness-110"><UserCog className="w-4 h-4" /> Manage</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => { if (!o) setEditing(null); }}>
        <DialogContent className="bg-royal-paper border-white/10 text-white max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-cinzel text-2xl text-gold flex items-center gap-2"><UserCog className="w-5 h-5" /> {editing?.display_name}</DialogTitle>
          </DialogHeader>
          <p className="text-white/50 text-sm">{editing?.email}</p>

          <div className="mt-4">
            <label className="block text-sm text-white/70 mb-2">Staff Role</label>
            <div className="flex gap-2" data-testid="staff-role-toggle">
              <button data-testid="staff-role-singer" onClick={() => setForm((f) => ({ ...f, role: 'singer' }))}
                className={`flex-1 rounded-lg px-3 py-2 border ${form.role === 'singer' ? 'bg-gold text-black font-semibold border-gold' : 'border-white/15 text-white/70'}`}>Singer (no staff)</button>
              <button data-testid="staff-role-kj" onClick={() => setForm((f) => ({ ...f, role: 'venue_kj' }))}
                className={`flex-1 rounded-lg px-3 py-2 border ${form.role === 'venue_kj' ? 'bg-gold text-black font-semibold border-gold' : 'border-white/15 text-white/70'}`}>Venue KJ</button>
            </div>
          </div>

          {form.role === 'venue_kj' && (
            <>
              <div className="mt-4 flex items-center justify-between p-3 rounded-lg border border-white/10">
                <div><p className="text-white font-medium">Staff access active</p><p className="text-white/40 text-xs">KJ can enter the Staff Portal only when active</p></div>
                <button data-testid="staff-active-toggle" onClick={() => setForm((f) => ({ ...f, staff_active: !f.staff_active }))}
                  className={`w-12 h-7 rounded-full transition relative ${form.staff_active ? 'bg-green-500' : 'bg-white/20'}`}>
                  <span className={`absolute top-1 w-5 h-5 bg-white rounded-full transition ${form.staff_active ? 'left-6' : 'left-1'}`} />
                </button>
              </div>

              <div className="mt-4">
                <label className="block text-sm text-white/70 mb-2 flex items-center gap-2"><Building2 className="w-4 h-4 text-gold" /> Authorized Venues</label>
                <div className="space-y-3 max-h-56 overflow-y-auto pr-1" data-testid="staff-venue-list">
                  {Object.keys(venuesByLocation).length === 0 && <p className="text-white/40 text-sm">No venues exist yet.</p>}
                  {Object.entries(venuesByLocation).map(([locId, vs]) => (
                    <div key={locId}>
                      <p className="text-white/40 text-xs uppercase tracking-wide mb-1">{locName(locId)}</p>
                      {vs.map((v) => (
                        <label key={v.id} data-testid={`staff-venue-${v.id}`} className="flex items-center gap-2 py-1 cursor-pointer">
                          <span className={`w-4 h-4 rounded border flex items-center justify-center ${form.venue_ids.includes(v.id) ? 'bg-gold border-gold' : 'border-white/30'}`}>
                            {form.venue_ids.includes(v.id) && <Check className="w-3 h-3 text-black" />}
                          </span>
                          <input type="checkbox" className="hidden" checked={form.venue_ids.includes(v.id)} onChange={() => toggleVenue(v.id)} />
                          <span className="text-white/80">{v.name}</span>
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          <div className="mt-6 flex gap-3">
            <button onClick={() => setEditing(null)} className="flex-1 rounded-lg px-4 py-2 border border-white/20 text-white/80 hover:bg-white/10">Cancel</button>
            <button data-testid="staff-save-btn" onClick={save} disabled={saving}
              className="flex-1 rounded-lg px-4 py-2 bg-gold text-black font-semibold hover:brightness-110 disabled:opacity-50">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </Phase2Shell>
  );
};

export default StaffPage;
