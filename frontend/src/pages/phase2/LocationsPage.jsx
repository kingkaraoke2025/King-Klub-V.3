import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Plus, Building2, Pencil, Trash2, Archive, ArchiveRestore, Clock, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell } from '@/components/Phase2Shell';
import { useAuth } from '@/context/AuthContext';
import { p2, isGlobalAdmin, errMsg } from '@/lib/phase2Api';

const empty = { name: '', city: '', state: '', country: 'USA', zip_code: '', timezone: '' };

const LocationsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);
  const [tz, setTz] = useState({ ok: null, timezone: '', label: '', place_name: '', error: '', loading: false });
  const canManage = isGlobalAdmin(user);

  const load = async () => {
    try {
      let locs = await p2.locations();
      if (!canManage) {
        const venues = await p2.venues().catch(() => []);
        const allowed = new Set(venues.map((v) => v.location_id));
        locs = locs.filter((l) => allowed.has(l.id));
      }
      setLocations(locs);
    } catch (e) { toast.error(errMsg(e, 'Failed to load locations')); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  // Live ZIP -> timezone lookup (debounced) whenever the ZIP in the open form changes.
  useEffect(() => {
    if (!form) return;
    const zip = (form.zip_code || '').trim();
    if (!/^\d{5}$/.test(zip)) {
      setTz({ ok: null, timezone: form.timezone || '', label: '', place_name: '', error: '', loading: false });
      return;
    }
    setTz((t) => ({ ...t, loading: true }));
    const h = setTimeout(async () => {
      try {
        const r = await p2.zipTimezone(zip);
        if (r.ok) {
          setTz({ ok: true, timezone: r.timezone, label: r.label, place_name: r.place_name, error: '', loading: false });
          setForm((f) => (f ? { ...f, timezone: r.timezone } : f));
        } else {
          setTz({ ok: false, timezone: '', label: '', place_name: '', error: r.error, loading: false });
          setForm((f) => (f ? { ...f, timezone: '' } : f));
        }
      } catch (e) { setTz({ ok: false, timezone: '', label: '', place_name: '', error: 'Lookup failed', loading: false }); }
    }, 450);
    return () => clearTimeout(h);
  }, [form?.zip_code]); // eslint-disable-line

  const openForm = (loc) => {
    const f = loc ? { ...loc } : { ...empty };
    setForm(f);
    setTz({ ok: loc?.timezone ? true : null, timezone: loc?.timezone || '', label: '', place_name: '', error: '', loading: false });
  };

  const save = async () => {
    if (!form.name?.trim()) { toast.error('Location name is required'); return; }
    if ((form.zip_code || '').trim() && tz.ok === false) { toast.error('Fix the ZIP code — timezone could not be determined'); return; }
    try {
      if (form.id) { await p2.updateLocation(form.id, form); toast.success('Location updated'); }
      else { await p2.createLocation(form); toast.success('Location created'); }
      setForm(null); load();
    } catch (e) { toast.error(errMsg(e, 'Save failed')); }
  };

  const doDelete = async (loc) => {
    if (!window.confirm(`Permanently delete "${loc.name}"? This only works if it has no venues/events/staff.`)) return;
    try { await p2.deleteLocation(loc.id); toast.success('Location deleted'); load(); }
    catch (e) {
      const d = e.response?.data?.detail;
      if (e.response?.status === 409 && d) {
        const dep = d.dependents || {};
        if (window.confirm(`Cannot delete — it has ${dep.venues} venue(s), ${dep.events} event(s), ${dep.staff_assignments} staff assignment(s). Archive it instead to preserve history?`)) {
          try { await p2.archiveLocation(loc.id); toast.success('Location archived'); load(); }
          catch (er) { toast.error(errMsg(er, 'Archive failed')); }
        }
      } else { toast.error(typeof d === 'string' ? d : 'Delete failed'); }
    }
  };

  const toggleArchive = async (loc) => {
    try {
      if (loc.archived) { await p2.unarchiveLocation(loc.id); toast.success('Location restored'); }
      else { await p2.archiveLocation(loc.id); toast.success('Location archived'); }
      load();
    } catch (e) { toast.error(errMsg(e, 'Failed')); }
  };

  return (
    <Phase2Shell
      title="Locations"
      subtitle="Manage locations, drill into venues and events"
      crumbs={[{ label: 'Locations' }]}
      actions={canManage && (
        <button data-testid="add-location-btn" onClick={() => openForm(null)}
          className="bg-gold text-black font-semibold px-4 py-2 rounded-full flex items-center gap-2 hover:brightness-110 transition">
          <Plus className="w-4 h-4" /> New Location
        </button>
      )}
    >
      {form && (
        <div className="glass-card p-5 mb-6 border border-gold/30" data-testid="location-form">
          <h3 className="font-cinzel text-lg text-gold mb-4">{form.id ? 'Edit' : 'New'} Location</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[['name', 'Name'], ['city', 'City'], ['state', 'State'], ['country', 'Country'], ['zip_code', 'ZIP Code']].map(([k, lbl]) => (
              <div key={k}>
                <label className="text-xs text-white/60">{lbl}</label>
                <input data-testid={`location-${k}-input`} value={form[k] || ''}
                  onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  inputMode={k === 'zip_code' ? 'numeric' : undefined}
                  maxLength={k === 'zip_code' ? 5 : undefined}
                  placeholder={k === 'zip_code' ? 'e.g. 84301' : ''}
                  className="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 mt-1 text-white focus:border-gold outline-none" />
              </div>
            ))}
            {/* Auto-determined, read-only timezone */}
            <div className="md:col-span-2">
              <label className="text-xs text-white/60">Timezone (auto-determined from ZIP)</label>
              <div data-testid="location-timezone-display"
                className={`w-full rounded-lg px-3 py-2 mt-1 flex items-center gap-2 border ${tz.ok === false ? 'border-red-500/50 bg-red-500/10' : 'border-white/15 bg-black/20'}`}>
                {tz.loading ? (
                  <span className="text-white/50 text-sm flex items-center gap-2"><Clock className="w-4 h-4 animate-spin" /> Determining…</span>
                ) : tz.ok === false ? (
                  <span className="text-red-300 text-sm flex items-center gap-2" data-testid="location-tz-warning"><AlertTriangle className="w-4 h-4" /> {tz.error}</span>
                ) : (form.timezone || tz.timezone) ? (
                  <span className="text-green-300 text-sm flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="font-mono text-white">{form.timezone || tz.timezone}</span>
                    {tz.label && <span className="text-white/60">({tz.label}{tz.place_name ? ` — ${tz.place_name}` : ''})</span>}
                  </span>
                ) : (
                  <span className="text-white/40 text-sm">Enter a ZIP code to determine the timezone.</span>
                )}
              </div>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button data-testid="location-save-btn" onClick={save} className="bg-gold text-black font-semibold px-4 py-2 rounded-full">Save</button>
            <button onClick={() => setForm(null)} className="px-4 py-2 rounded-full border border-white/20 text-white/70">Cancel</button>
          </div>
        </div>
      )}

      {loading ? <p className="text-white/50">Loading…</p> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="locations-grid">
          {locations.length === 0 && <p className="text-white/50">No locations yet.</p>}
          {locations.map((loc) => (
            <div key={loc.id} data-testid={`location-card-${loc.id}`}
              className={`glass-card p-5 border transition group ${loc.archived ? 'border-white/5 opacity-60' : 'border-white/10 hover:border-gold/40'}`}>
              <div className="flex items-start justify-between">
                <MapPin className="w-6 h-6 text-gold" />
                {canManage && (
                  <div className="flex items-center gap-1">
                    <button data-testid={`edit-location-${loc.id}`} onClick={() => openForm(loc)} className="text-white/40 hover:text-gold p-1" title="Edit"><Pencil className="w-4 h-4" /></button>
                    <button data-testid={`archive-location-${loc.id}`} onClick={() => toggleArchive(loc)} className="text-white/40 hover:text-blue-300 p-1" title={loc.archived ? 'Restore' : 'Archive'}>
                      {loc.archived ? <ArchiveRestore className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
                    </button>
                    <button data-testid={`delete-location-${loc.id}`} onClick={() => doDelete(loc)} className="text-white/40 hover:text-red-400 p-1" title="Delete"><Trash2 className="w-4 h-4" /></button>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 mt-3">
                <h3 className="font-cinzel text-xl text-white">{loc.name}</h3>
                {loc.archived && <span data-testid={`archived-badge-${loc.id}`} className="text-xs bg-white/10 text-white/60 px-2 py-0.5 rounded">Archived</span>}
              </div>
              <p className="text-white/50 text-sm">{[loc.city, loc.state, loc.zip_code].filter(Boolean).join(', ')}</p>
              <p className="text-white/40 text-xs mt-1 flex items-center gap-1"><Clock className="w-3 h-3" /> {loc.timezone}</p>
              <button data-testid={`open-location-${loc.id}`} onClick={() => navigate(`/admin/phase2/locations/${loc.id}`)}
                className="mt-4 w-full flex items-center justify-center gap-2 border border-gold/40 text-gold rounded-full py-2 hover:bg-gold/10 transition">
                <Building2 className="w-4 h-4" /> View Venues
              </button>
            </div>
          ))}
        </div>
      )}
    </Phase2Shell>
  );
};

export default LocationsPage;
