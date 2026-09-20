import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Building2, Plus, CalendarDays, Pencil, Trash2, Archive, ArchiveRestore } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell } from '@/components/Phase2Shell';
import { useAuth } from '@/context/AuthContext';
import { p2, isGlobalAdmin } from '@/lib/phase2Api';
const VenuesPage = () => {
  const { locationId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [venues, setVenues] = useState([]);
  const [location, setLocation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);
  const canCreate = isGlobalAdmin(user) || user?.role === 'location_manager';
  const canManage = canCreate || (user?.role === 'venue_kj' && user?.staff_active);

  const load = async () => {
    try {
      const [vs, locs] = await Promise.all([p2.venues(locationId), p2.locations().catch(() => [])]);
      setVenues(vs);
      setLocation(locs.find((l) => l.id === locationId) || null);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to load venues'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [locationId]);

  const save = async () => {
    try {
      if (form.id) { await p2.updateVenue(form.id, { ...form, location_id: locationId }); toast.success('Venue updated'); }
      else { await p2.createVenue({ ...form, location_id: locationId }); toast.success('Venue created'); }
      setForm(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
  };

  const doDelete = async (v) => {
    if (!window.confirm(`Permanently delete venue "${v.name}"? Only works if it has no events/staff.`)) return;
    try { await p2.deleteVenue(v.id); toast.success('Venue deleted'); load(); }
    catch (e) {
      const d = e.response?.data?.detail;
      if (e.response?.status === 409 && d) {
        const dep = d.dependents || {};
        if (window.confirm(`Cannot delete — ${dep.events} event(s), ${dep.staff_assignments} other staff assignment(s). Archive instead to preserve history?`)) {
          try { await p2.archiveVenue(v.id); toast.success('Venue archived'); load(); } catch (er) { toast.error('Archive failed'); }
        }
      } else { toast.error(typeof d === 'string' ? d : 'Delete failed'); }
    }
  };
  const toggleArchive = async (v) => {
    try { await (v.archived ? p2.unarchiveVenue(v.id) : p2.archiveVenue(v.id)); toast.success(v.archived ? 'Venue restored' : 'Venue archived'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  return (
    <Phase2Shell
      title={location ? `${location.name} — Venues` : 'Venues'}
      subtitle="Venues in this location"
      back="/admin/phase2"
      crumbs={[{ label: 'Locations', to: '/admin/phase2' }, { label: location?.name || 'Venues' }]}
      actions={canCreate && (
        <button data-testid="add-venue-btn" onClick={() => setForm({ name: '', address: '', timezone: '' })}
          className="bg-gold text-black font-semibold px-4 py-2 rounded-full flex items-center gap-2 hover:brightness-110 transition">
          <Plus className="w-4 h-4" /> New Venue
        </button>
      )}
    >
      {form && (
        <div className="glass-card p-5 mb-6 border border-gold/30" data-testid="venue-form">
          <h3 className="font-cinzel text-lg text-gold mb-4">{form.id ? 'Edit' : 'New'} Venue</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[['name', 'Name'], ['address', 'Address'], ['timezone', 'Timezone (blank = inherit)']].map(([k, lbl]) => (
              <div key={k}>
                <label className="text-xs text-white/60">{lbl}</label>
                <input data-testid={`venue-${k}-input`} value={form[k] || ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  className="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 mt-1 text-white focus:border-gold outline-none" />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button data-testid="venue-save-btn" onClick={save} className="bg-gold text-black font-semibold px-4 py-2 rounded-full">Save</button>
            <button onClick={() => setForm(null)} className="px-4 py-2 rounded-full border border-white/20 text-white/70">Cancel</button>
          </div>
        </div>
      )}

      {loading ? <p className="text-white/50">Loading…</p> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="venues-grid">
          {venues.length === 0 && <p className="text-white/50">No venues in this location.</p>}
          {venues.map((v) => (
            <div key={v.id} data-testid={`venue-card-${v.id}`} className={`glass-card p-5 border transition ${v.archived ? 'border-white/5 opacity-60' : 'border-white/10 hover:border-gold/40'}`}>
              <div className="flex items-start justify-between">
                <Building2 className="w-6 h-6 text-gold" />
                {canManage && (
                  <div className="flex items-center gap-1">
                    <button data-testid={`edit-venue-${v.id}`} onClick={() => setForm({ ...v })} className="text-white/40 hover:text-gold p-1" title="Edit"><Pencil className="w-4 h-4" /></button>
                    <button data-testid={`archive-venue-${v.id}`} onClick={() => toggleArchive(v)} className="text-white/40 hover:text-blue-300 p-1" title={v.archived ? 'Restore' : 'Archive'}>{v.archived ? <ArchiveRestore className="w-4 h-4" /> : <Archive className="w-4 h-4" />}</button>
                    <button data-testid={`delete-venue-${v.id}`} onClick={() => doDelete(v)} className="text-white/40 hover:text-red-400 p-1" title="Delete"><Trash2 className="w-4 h-4" /></button>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 mt-3">
                <h3 className="font-cinzel text-xl text-white">{v.name}</h3>
                {v.archived && <span data-testid={`venue-archived-${v.id}`} className="text-xs bg-white/10 text-white/60 px-2 py-0.5 rounded">Archived</span>}
              </div>
              <p className="text-white/50 text-sm">{v.address || '—'}</p>
              <button data-testid={`open-venue-${v.id}`} onClick={() => navigate(`/admin/phase2/venues/${v.id}`)}
                className="mt-4 w-full flex items-center justify-center gap-2 border border-gold/40 text-gold rounded-full py-2 hover:bg-gold/10 transition">
                <CalendarDays className="w-4 h-4" /> View Events
              </button>
            </div>
          ))}
        </div>
      )}
    </Phase2Shell>
  );
};

export default VenuesPage;
