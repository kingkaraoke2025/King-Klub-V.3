import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Plus, Building2, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell } from '@/components/Phase2Shell';
import { useAuth } from '@/context/AuthContext';
import { p2, isGlobalAdmin } from '@/lib/phase2Api';

const empty = { name: '', city: '', state: '', country: 'USA', timezone: 'America/Chicago' };

const LocationsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);
  const canManage = isGlobalAdmin(user);

  const load = async () => {
    try {
      let locs = await p2.locations();
      // Role-based UI scoping: non-global-admin sees only locations that contain
      // a venue they are scoped to (backend remains authoritative).
      if (!canManage) {
        const venues = await p2.venues().catch(() => []);
        const allowed = new Set(venues.map((v) => v.location_id));
        locs = locs.filter((l) => allowed.has(l.id));
      }
      setLocations(locs);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to load locations'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      if (form.id) { await p2.updateLocation(form.id, form); toast.success('Location updated'); }
      else { await p2.createLocation(form); toast.success('Location created'); }
      setForm(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
  };

  return (
    <Phase2Shell
      title="Locations"
      subtitle="Manage locations, drill into venues and events"
      crumbs={[{ label: 'Locations' }]}
      actions={canManage && (
        <button data-testid="add-location-btn" onClick={() => setForm({ ...empty })}
          className="bg-gold text-black font-semibold px-4 py-2 rounded-full flex items-center gap-2 hover:brightness-110 transition">
          <Plus className="w-4 h-4" /> New Location
        </button>
      )}
    >
      {form && (
        <div className="glass-card p-5 mb-6 border border-gold/30" data-testid="location-form">
          <h3 className="font-cinzel text-lg text-gold mb-4">{form.id ? 'Edit' : 'New'} Location</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[['name', 'Name'], ['city', 'City'], ['state', 'State'], ['country', 'Country'], ['timezone', 'Timezone (IANA)']].map(([k, lbl]) => (
              <div key={k}>
                <label className="text-xs text-white/60">{lbl}</label>
                <input data-testid={`location-${k}-input`} value={form[k] || ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  className="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 mt-1 text-white focus:border-gold outline-none" />
              </div>
            ))}
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
              className="glass-card p-5 border border-white/10 hover:border-gold/40 transition group">
              <div className="flex items-start justify-between">
                <MapPin className="w-6 h-6 text-gold" />
                {canManage && (
                  <button data-testid={`edit-location-${loc.id}`} onClick={() => setForm({ ...loc })}
                    className="text-white/40 hover:text-gold"><Pencil className="w-4 h-4" /></button>
                )}
              </div>
              <h3 className="font-cinzel text-xl text-white mt-3">{loc.name}</h3>
              <p className="text-white/50 text-sm">{[loc.city, loc.state].filter(Boolean).join(', ')} · {loc.timezone}</p>
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
