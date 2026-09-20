import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CalendarDays, Plus, Settings, Pencil, Trash2, Archive, ArchiveRestore } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell, StatusBadge } from '@/components/Phase2Shell';
import { p2 } from '@/lib/phase2Api';

const STATUSES = ['draft', 'scheduled', 'active', 'ended', 'cancelled', 'archived'];
const emptyEvent = { name: '', event_date: '', status: 'scheduled', starts_at: '', ends_at: '' };

const EventsPage = () => {
  const { venueId } = useParams();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [venue, setVenue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);

  const load = async () => {
    try {
      const [all, venues] = await Promise.all([p2.events(), p2.venues().catch(() => [])]);
      setEvents(all.filter((e) => e.venue_id === venueId));
      setVenue(venues.find((v) => v.id === venueId) || null);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to load events'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [venueId]);

  const save = async () => {
    try {
      if (form.id) { await p2.updateEvent(form.id, form); toast.success('Event updated'); }
      else { await p2.createEvent({ ...form, venue_id: venueId }); toast.success('Event created'); }
      setForm(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
  };

  const doDelete = async (ev) => {
    if (!window.confirm(`Permanently delete event "${ev.name}"? Only works if it has no history.`)) return;
    try { await p2.deleteEvent(ev.id); toast.success('Event deleted'); load(); }
    catch (e) {
      const d = e.response?.data?.detail;
      if (e.response?.status === 409 && d) {
        const dep = d.dependents || {};
        if (window.confirm(`Cannot delete — ${dep.participants} participant(s), ${dep.queue_items} queue, ${dep.battles} battle(s), ${dep.point_history} point record(s). Archive instead to preserve history?`)) {
          try { await p2.archiveEvent(ev.id); toast.success('Event archived'); load(); } catch (er) { toast.error('Archive failed'); }
        }
      } else { toast.error(typeof d === 'string' ? d : 'Delete failed'); }
    }
  };
  const toggleArchive = async (ev) => {
    try { await (ev.status === 'archived' ? p2.unarchiveEvent(ev.id) : p2.archiveEvent(ev.id)); toast.success(ev.status === 'archived' ? 'Event restored' : 'Event archived'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  return (
    <Phase2Shell
      title={venue ? `${venue.name} — Events` : 'Events'}
      subtitle="Events scoped to this venue"
      back={venue ? `/admin/phase2/locations/${venue.location_id}` : '/admin/phase2'}
      crumbs={[{ label: 'Locations', to: '/admin/phase2' }, { label: venue?.name || 'Venue' }, { label: 'Events' }]}
      actions={(
        <button data-testid="add-event-btn" onClick={() => setForm({ ...emptyEvent })}
          className="bg-gold text-black font-semibold px-4 py-2 rounded-full flex items-center gap-2 hover:brightness-110 transition">
          <Plus className="w-4 h-4" /> New Event
        </button>
      )}
    >
      {form && (
        <div className="glass-card p-5 mb-6 border border-gold/30" data-testid="event-form">
          <h3 className="font-cinzel text-lg text-gold mb-4">{form.id ? 'Edit' : 'New'} Event</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-white/60">Name</label>
              <input data-testid="event-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 mt-1 text-white focus:border-gold outline-none" />
            </div>
            <div>
              <label className="text-xs text-white/60">Event Date (YYYY-MM-DD)</label>
              <input data-testid="event-date-input" type="date" value={form.event_date} onChange={(e) => setForm({ ...form, event_date: e.target.value })}
                className="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 mt-1 text-white focus:border-gold outline-none" />
            </div>
            <div>
              <label className="text-xs text-white/60">Status</label>
              <select data-testid="event-status-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 mt-1 text-white focus:border-gold outline-none">
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button data-testid="event-save-btn" onClick={save} className="bg-gold text-black font-semibold px-4 py-2 rounded-full">Save</button>
            <button onClick={() => setForm(null)} className="px-4 py-2 rounded-full border border-white/20 text-white/70">Cancel</button>
          </div>
        </div>
      )}

      {loading ? <p className="text-white/50">Loading…</p> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="events-grid">
          {events.length === 0 && <p className="text-white/50">No events for this venue.</p>}
          {events.map((ev) => (
            <div key={ev.id} data-testid={`event-card-${ev.id}`} className="glass-card p-5 border border-white/10 hover:border-gold/40 transition">
              <div className="flex items-start justify-between">
                <CalendarDays className="w-6 h-6 text-gold" />
                <div className="flex items-center gap-1">
                  <StatusBadge status={ev.status} />
                  <button data-testid={`edit-event-${ev.id}`} onClick={() => setForm({ ...ev })} className="text-white/40 hover:text-gold p-1" title="Edit"><Pencil className="w-4 h-4" /></button>
                  <button data-testid={`archive-event-${ev.id}`} onClick={() => toggleArchive(ev)} className="text-white/40 hover:text-blue-300 p-1" title={ev.status === 'archived' ? 'Restore' : 'Archive'}>{ev.status === 'archived' ? <ArchiveRestore className="w-4 h-4" /> : <Archive className="w-4 h-4" />}</button>
                  <button data-testid={`delete-event-${ev.id}`} onClick={() => doDelete(ev)} className="text-white/40 hover:text-red-400 p-1" title="Delete"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <h3 className="font-cinzel text-xl text-white mt-3">{ev.name}</h3>
              <p className="text-white/50 text-sm">{ev.event_date}</p>
              <button data-testid={`manage-event-${ev.id}`} onClick={() => navigate(`/admin/phase2/events/${ev.id}`)}
                className="mt-4 w-full flex items-center justify-center gap-2 border border-gold/40 text-gold rounded-full py-2 hover:bg-gold/10 transition">
                <Settings className="w-4 h-4" /> Manage Event
              </button>
            </div>
          ))}
        </div>
      )}
    </Phase2Shell>
  );
};

export default EventsPage;
