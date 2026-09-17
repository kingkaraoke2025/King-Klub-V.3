import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { LayoutGrid, QrCode, Users, ListMusic, Trophy, RefreshCw, Copy, Check, ChevronUp, ChevronDown, Play, Award } from 'lucide-react';
import { toast } from 'sonner';
import { Phase2Shell, StatusBadge } from '@/components/Phase2Shell';
import { p2, qrImage, FRONTEND_URL } from '@/lib/phase2Api';

const TABS = [
  { k: 'overview', label: 'Overview', icon: LayoutGrid },
  { k: 'qr', label: 'QR', icon: QrCode },
  { k: 'singers', label: 'Singers', icon: Users },
  { k: 'queue', label: 'Queue', icon: ListMusic },
  { k: 'leaderboard', label: 'Points/Leaderboard', icon: Trophy },
];

const EventManagePage = () => {
  const { eventId } = useParams();
  const [tab, setTab] = useState('overview');
  const [event, setEvent] = useState(null);
  const [qr, setQr] = useState(null);
  const [singers, setSingers] = useState([]);
  const [queue, setQueue] = useState([]);
  const [board, setBoard] = useState({ mode: 'event', rows: [] });
  const [copied, setCopied] = useState(false);

  const loadEvent = useCallback(async () => {
    try { setEvent(await p2.event(eventId)); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed to load event'); }
  }, [eventId]);
  useEffect(() => { loadEvent(); }, [loadEvent]);

  const loadQR = async () => {
    try { setQr(await p2.eventQR(eventId)); } catch (e) { toast.error(e.response?.data?.detail || 'QR failed'); }
  };
  const loadSingers = async () => {
    try { setSingers((await p2.singerList(eventId)).singers); } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };
  const loadQueue = async () => {
    try { setQueue(await p2.eventQueue(eventId)); } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };
  const loadEventBoard = async () => {
    try { setBoard({ mode: 'event', rows: (await p2.eventLeaderboard(eventId)).leaderboard }); } catch (e) { toast.error('Failed'); }
  };
  const loadSeasonBoard = async () => {
    try { setBoard({ mode: 'season', rows: (await p2.seasonLeaderboard()).leaderboard }); } catch (e) { toast.error('Failed'); }
  };

  useEffect(() => {
    if (tab === 'qr' && !qr) loadQR();
    if (tab === 'singers') loadSingers();
    if (tab === 'queue') loadQueue();
    if (tab === 'leaderboard') loadEventBoard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const checkinUrl = qr ? `${FRONTEND_URL}${qr.checkin_path}` : '';
  const copy = () => { navigator.clipboard.writeText(checkinUrl); setCopied(true); toast.success('Check-in URL copied'); setTimeout(() => setCopied(false), 1500); };

  const qCtl = async (fn, ...args) => { try { await fn(...args); loadQueue(); } catch (e) { toast.error(e.response?.data?.detail || 'Action failed'); } };

  const award = async (userId) => {
    const pts = parseInt(window.prompt('Award how many event points to this singer?', '10'), 10);
    if (!pts || pts <= 0) return;
    try { await p2.awardPoints(eventId, { user_id: userId, points: pts, action_id: 'sing_song' }); toast.success(`Awarded ${pts} pts`); loadSingers(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Award failed'); }
  };

  return (
    <Phase2Shell
      title={event ? event.name : 'Event'}
      subtitle={event ? `${event.event_date}` : ''}
      back={event ? `/admin/phase2/venues/${event.venue_id}` : '/admin/phase2'}
      crumbs={[{ label: 'Locations', to: '/admin/phase2' }, { label: 'Event', }, { label: event?.name || '' }]}
      actions={event && <StatusBadge status={event.status} />}
    >
      <div className="flex gap-2 flex-wrap mb-6 border-b border-white/10 pb-3" data-testid="event-tabs">
        {TABS.map((t) => (
          <button key={t.k} data-testid={`tab-${t.k}`} onClick={() => setTab(t.k)}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition ${tab === t.k ? 'bg-gold text-black font-semibold' : 'text-white/60 hover:text-gold border border-white/10'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && event && (
        <div className="glass-card p-6 border border-white/10 space-y-3" data-testid="event-overview">
          {[['Event', event.name], ['Date', event.event_date], ['Status', event.status], ['Venue ID', event.venue_id], ['Location ID', event.location_id], ['Event ID', event.id]].map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-white/5 pb-2">
              <span className="text-white/50">{k}</span><span className="text-white/90 font-mono text-sm">{v}</span>
            </div>
          ))}
        </div>
      )}

      {tab === 'qr' && (
        <div className="glass-card p-6 border border-white/10 flex flex-col items-center text-center" data-testid="event-qr-panel">
          <div className="text-white/60 mb-2">Event QR for <span className="text-gold font-semibold">{event?.name}</span></div>
          {qr ? (
            <>
              <img src={qrImage(checkinUrl)} alt="Event QR" className="rounded-xl border border-gold/30 bg-[#1A0B2E] p-2" data-testid="event-qr-image" />
              <div className="mt-4 w-full max-w-lg">
                <div className="flex items-center gap-2 bg-black/40 border border-white/15 rounded-lg px-3 py-2">
                  <span className="text-white/70 text-sm truncate flex-1 text-left" data-testid="event-qr-url">{checkinUrl}</span>
                  <button data-testid="copy-qr-url-btn" onClick={copy} className="text-gold hover:brightness-110">{copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}</button>
                </div>
                <p className="text-white/40 text-xs mt-2">Expires: {qr.expires_at ? new Date(qr.expires_at).toLocaleString() : 'n/a'}</p>
                <button data-testid="refresh-qr-btn" onClick={loadQR} className="mt-4 inline-flex items-center gap-2 border border-gold/40 text-gold rounded-full px-4 py-2 hover:bg-gold/10">
                  <RefreshCw className="w-4 h-4" /> Regenerate QR
                </button>
              </div>
            </>
          ) : <button onClick={loadQR} data-testid="generate-qr-btn" className="bg-gold text-black font-semibold px-4 py-2 rounded-full">Generate QR</button>}
        </div>
      )}

      {tab === 'singers' && (
        <div className="glass-card p-4 border border-white/10" data-testid="singers-panel">
          <table className="w-full text-sm">
            <thead><tr className="text-white/50 text-left border-b border-white/10">
              <th className="py-2 px-2">#</th><th className="px-2">Singer</th><th className="px-2">Status</th><th className="px-2">Event Pts</th><th className="px-2">Songs</th><th className="px-2"></th>
            </tr></thead>
            <tbody data-testid="singers-tbody">
              {singers.length === 0 && <tr><td colSpan="6" className="text-white/40 py-4 px-2">No singers checked in yet.</td></tr>}
              {singers.map((s) => (
                <tr key={s.user_id} className="border-b border-white/5" data-testid={`singer-row-${s.user_id}`}>
                  <td className="py-2 px-2 text-gold">{s.list_position}</td>
                  <td className="px-2">{s.display_name}</td>
                  <td className="px-2"><StatusBadge status={s.status} /></td>
                  <td className="px-2">{s.event_points}</td>
                  <td className="px-2">{s.songs_performed}</td>
                  <td className="px-2 text-right"><button data-testid={`award-${s.user_id}`} onClick={() => award(s.user_id)} className="text-gold hover:brightness-110 inline-flex items-center gap-1"><Award className="w-4 h-4" /> Award</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'queue' && (
        <div className="glass-card p-4 border border-white/10" data-testid="queue-panel">
          <table className="w-full text-sm">
            <thead><tr className="text-white/50 text-left border-b border-white/10">
              <th className="py-2 px-2">#</th><th className="px-2">Song</th><th className="px-2">Singer</th><th className="px-2">Status</th><th className="px-2">KJ Controls</th>
            </tr></thead>
            <tbody data-testid="queue-tbody">
              {queue.length === 0 && <tr><td colSpan="5" className="text-white/40 py-4 px-2">Queue is empty.</td></tr>}
              {queue.map((q) => (
                <tr key={q.id} className="border-b border-white/5" data-testid={`queue-row-${q.id}`}>
                  <td className="py-2 px-2 text-gold">{q.position}</td>
                  <td className="px-2">{q.song_title} <span className="text-white/40">— {q.artist}</span></td>
                  <td className="px-2">{q.user_name}</td>
                  <td className="px-2"><StatusBadge status={q.status} /></td>
                  <td className="px-2">
                    <div className="flex items-center gap-1">
                      <button data-testid={`q-up-${q.id}`} onClick={() => qCtl(p2.moveUp, eventId, q.id)} className="p-1 text-white/60 hover:text-gold"><ChevronUp className="w-4 h-4" /></button>
                      <button data-testid={`q-down-${q.id}`} onClick={() => qCtl(p2.moveDown, eventId, q.id)} className="p-1 text-white/60 hover:text-gold"><ChevronDown className="w-4 h-4" /></button>
                      <button data-testid={`q-current-${q.id}`} onClick={() => qCtl(p2.setCurrent, eventId, q.id)} className="p-1 text-white/60 hover:text-gold"><Play className="w-4 h-4" /></button>
                      <button data-testid={`q-complete-${q.id}`} onClick={() => qCtl(p2.completeSong, eventId, q.id)} className="p-1 text-green-400 hover:brightness-125"><Check className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'leaderboard' && (
        <div className="glass-card p-4 border border-white/10" data-testid="leaderboard-panel">
          <div className="flex gap-2 mb-4">
            <button data-testid="lb-event-btn" onClick={loadEventBoard} className={`px-3 py-1.5 rounded-full text-sm ${board.mode === 'event' ? 'bg-gold text-black' : 'border border-white/15 text-white/60'}`}>This Event</button>
            <button data-testid="lb-season-btn" onClick={loadSeasonBoard} className={`px-3 py-1.5 rounded-full text-sm ${board.mode === 'season' ? 'bg-gold text-black' : 'border border-white/15 text-white/60'}`}>Current Season</button>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-white/50 text-left border-b border-white/10">
              <th className="py-2 px-2">#</th><th className="px-2">Singer</th><th className="px-2">{board.mode === 'season' ? 'Season Pts' : 'Event Pts'}</th>{board.mode === 'season' && <th className="px-2">Rank</th>}
            </tr></thead>
            <tbody data-testid="leaderboard-tbody">
              {board.rows.length === 0 && <tr><td colSpan="4" className="text-white/40 py-4 px-2">No entries.</td></tr>}
              {board.rows.map((r) => (
                <tr key={r.user_id} className="border-b border-white/5" data-testid={`lb-row-${r.user_id}`}>
                  <td className="py-2 px-2 text-gold">{r.position}</td>
                  <td className="px-2">{r.display_name}</td>
                  <td className="px-2">{board.mode === 'season' ? r.season_points : r.event_points}</td>
                  {board.mode === 'season' && <td className="px-2 text-white/60">{r.rank}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Phase2Shell>
  );
};

export default EventManagePage;
