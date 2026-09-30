import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, CalendarDays, PlayCircle, QrCode, Users, Trophy, Star } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell, StatusBadge } from '@/components/Phase2Shell';
import { p2, errMsg } from '@/lib/phase2Api';

// KJ Console: a KJ's home for running a show. Lists the events they're authorized
// for (backend-scoped GET /admin/events), grouped by venue, and lets them SELECT
// the show they're running. Selecting opens the event workflow (QR -> check-in ->
// singers -> queue -> points -> perks -> leaderboard), all event-scoped.
const ACTIVE = ['active', 'scheduled'];

const KJConsolePage = () => {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [venues, setVenues] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [evs, vns] = await Promise.all([p2.events(), p2.venues().catch(() => [])]);
        setEvents(evs);
        setVenues(vns);
      } catch (e) {
        toast.error(errMsg(e, 'Failed to load your shows'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const venueName = (id) => venues.find((v) => v.id === id)?.name || 'Your Venue';

  // Group events by venue; split active/upcoming vs past.
  const grouped = useMemo(() => {
    const g = {};
    for (const e of events) {
      (g[e.venue_id] = g[e.venue_id] || { upcoming: [], past: [] });
      (ACTIVE.includes(e.status) ? g[e.venue_id].upcoming : g[e.venue_id].past).push(e);
    }
    Object.values(g).forEach((v) => {
      v.upcoming.sort((a, b) => (a.event_date || '').localeCompare(b.event_date || ''));
      v.past.sort((a, b) => (b.event_date || '').localeCompare(a.event_date || ''));
    });
    return g;
  }, [events]);

  const venueIds = Object.keys(grouped);
  const totalUpcoming = venueIds.reduce((n, vid) => n + grouped[vid].upcoming.length, 0);

  const runShow = (ev) => navigate(`/admin/phase2/events/${ev.id}`);

  const EventRow = ({ ev, highlight }) => (
    <div data-testid={`kj-event-${ev.id}`}
      className={`flex items-center justify-between gap-4 p-4 rounded-xl border transition ${highlight ? 'border-gold/50 bg-gold/5' : 'border-white/10 hover:border-gold/30'}`}>
      <div className="flex items-center gap-3 min-w-0">
        <CalendarDays className="w-5 h-5 text-gold shrink-0" />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-white font-cinzel truncate">{ev.name}</span>
            {highlight && <span className="text-[10px] uppercase tracking-wide text-gold border border-gold/40 rounded-full px-2 py-0.5">Default</span>}
          </div>
          <p className="text-white/50 text-sm">{ev.event_date}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <StatusBadge status={ev.status} />
        <button data-testid={`kj-run-${ev.id}`} onClick={() => runShow(ev)}
          className="bg-gold text-black font-semibold px-4 py-2 rounded-full flex items-center gap-2 hover:brightness-110 transition">
          <PlayCircle className="w-4 h-4" /> Run Show
        </button>
      </div>
    </div>
  );

  return (
    <Phase2Shell
      title="KJ Console"
      subtitle="Pick the show you're running tonight"
      crumbs={[{ label: 'KJ Console' }]}
    >
      {/* Quick capability legend */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8" data-testid="kj-capabilities">
        {[[QrCode, 'Event QR'], [Users, 'Singer List'], [Star, 'Queue & Perks'], [Trophy, 'Points & Leaderboard']].map(([Icon, label], i) => (
          <div key={i} className="glass-card p-4 flex items-center gap-3 border border-white/10">
            <Icon className="w-5 h-5 text-gold" /><span className="text-white/80 text-sm">{label}</span>
          </div>
        ))}
      </div>

      {loading ? (
        <p className="text-white/50">Loading your shows…</p>
      ) : venueIds.length === 0 ? (
        <div className="glass-card p-8 text-center border border-white/10" data-testid="kj-no-venue">
          <Building2 className="w-10 h-10 text-white/20 mx-auto mb-3" />
          <p className="text-white/60">No venue or events are assigned to you yet. Ask a global admin to assign your venue and create events.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {venueIds.map((vid) => {
            const { upcoming, past } = grouped[vid];
            const onlyOneActive = upcoming.length === 1;
            return (
              <div key={vid} className="glass-card p-6 border border-white/10" data-testid={`kj-venue-${vid}`}>
                <div className="flex items-center gap-3 mb-1">
                  <Building2 className="w-6 h-6 text-gold" />
                  <h2 className="font-cinzel text-2xl text-white">Venue: <span className="text-gold">{venueName(vid)}</span></h2>
                </div>
                <p className="text-white/40 text-sm mb-5">Active / Upcoming Shows</p>

                <div className="space-y-3" data-testid={`kj-upcoming-${vid}`}>
                  {upcoming.length === 0 && <p className="text-white/40">No active or upcoming shows. Ask an admin to schedule one.</p>}
                  {upcoming.map((ev) => <EventRow key={ev.id} ev={ev} highlight={onlyOneActive} />)}
                </div>

                {past.length > 0 && (
                  <details className="mt-5">
                    <summary className="text-white/40 text-sm cursor-pointer hover:text-gold">Past / ended shows ({past.length})</summary>
                    <div className="space-y-3 mt-3 opacity-70" data-testid={`kj-past-${vid}`}>
                      {past.map((ev) => <EventRow key={ev.id} ev={ev} />)}
                    </div>
                  </details>
                )}
              </div>
            );
          })}
          {totalUpcoming === 0 && (
            <p className="text-white/40 text-sm">Tip: only active/scheduled shows can be run. Ask a global admin to set an event to "active".</p>
          )}
        </div>
      )}
    </Phase2Shell>
  );
};

export default KJConsolePage;
