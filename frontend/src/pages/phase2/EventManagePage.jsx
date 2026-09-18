import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  LayoutGrid, QrCode, Users, ListMusic, Trophy, RefreshCw, Copy, Check, ChevronUp,
  ChevronDown, Play, Award, XCircle, GripVertical, Lock, Mic2, Swords, Vote, Crown, Gift,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Phase2Shell, StatusBadge } from '@/components/Phase2Shell';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { p2, qrImage, FRONTEND_URL } from '@/lib/phase2Api';

const TABS = [
  { k: 'overview', label: 'Overview', icon: LayoutGrid },
  { k: 'qr', label: 'QR Check-In', icon: QrCode },
  { k: 'singers', label: 'Singers', icon: Users },
  { k: 'queue', label: 'Queue', icon: ListMusic },
  { k: 'battles', label: 'Battles', icon: Swords },
  { k: 'leaderboard', label: 'Points/Leaderboard', icon: Trophy },
];

// ---- Sortable queue row (KJ controls) --------------------------------------
const SortableQueueRow = ({ item, pendingLen, onUp, onDown, onCurrent, onComplete, onRemove }) => {
  const locked = item.perk_protected && item.position <= 4;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.id, disabled: locked });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1, zIndex: isDragging ? 50 : 1 };
  return (
    <div ref={setNodeRef} style={style} data-testid={`queue-row-${item.id}`}
      className={`glass-card p-4 border ${item.perk_protected ? 'border-gold/40' : 'border-white/10'}`}>
      <div className="flex items-center gap-4">
        <div {...attributes} {...listeners}
          className={`p-1 rounded ${locked ? 'opacity-30 cursor-not-allowed' : 'cursor-grab active:cursor-grabbing hover:bg-white/10'}`}
          title={locked ? 'Perk protected — cannot move' : 'Drag to reorder'} data-testid={`q-drag-${item.id}`}>
          <GripVertical className="w-5 h-5 text-white/50" />
        </div>
        <div className="relative">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${item.perk_protected ? 'bg-gold/20' : 'bg-white/5'}`}>
            <span className="font-cinzel font-bold text-gold">{item.position}</span>
          </div>
          {item.perk_protected && (
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-gold rounded-full flex items-center justify-center" title="Perk protected">
              <Lock className="w-2.5 h-2.5 text-purple-deep" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-white truncate">{item.user_name}</h3>
            {item.perk_protected && <span className="text-xs bg-gold/20 text-gold px-1.5 py-0.5 rounded shrink-0">Perk Used</span>}
          </div>
          <p className="text-gold text-sm truncate">{item.song_title} — {item.artist}</p>
          {item.message_to_admin && (
            <div className="mt-2 p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg" data-testid={`q-msg-${item.id}`}>
              <p className="text-purple-300 text-xs font-medium mb-1">Message from singer:</p>
              <p className="text-white/80 text-sm break-words whitespace-pre-wrap">{item.message_to_admin}</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex flex-col gap-1">
            <button data-testid={`q-up-${item.id}`} onClick={() => onUp(item.id)} disabled={item.position === 1 || locked}
              className="h-6 w-6 flex items-center justify-center rounded border border-white/20 text-white/70 hover:bg-white/10 disabled:opacity-30"><ChevronUp className="w-4 h-4" /></button>
            <button data-testid={`q-down-${item.id}`} onClick={() => onDown(item.id)} disabled={item.position === pendingLen || locked}
              className="h-6 w-6 flex items-center justify-center rounded border border-white/20 text-white/70 hover:bg-white/10 disabled:opacity-30"><ChevronDown className="w-4 h-4" /></button>
          </div>
          <button data-testid={`q-current-${item.id}`} onClick={() => onCurrent(item.id)}
            className="h-8 px-2 flex items-center rounded bg-green-600 hover:bg-green-700 text-white" title="Set current"><Play className="w-4 h-4" /></button>
          <button data-testid={`q-complete-${item.id}`} onClick={() => onComplete(item.id)}
            className="h-8 px-2 flex items-center rounded border border-green-400/40 text-green-400 hover:bg-green-400/10" title="Complete"><Check className="w-4 h-4" /></button>
          <button data-testid={`q-remove-${item.id}`} onClick={() => onRemove(item.id)}
            className="h-8 px-2 flex items-center rounded bg-red-600/80 hover:bg-red-600 text-white" title="Remove"><XCircle className="w-4 h-4" /></button>
        </div>
      </div>
    </div>
  );
};

const EventManagePage = () => {
  const { eventId } = useParams();
  const [tab, setTab] = useState('overview');
  const [event, setEvent] = useState(null);
  const [venueName, setVenueName] = useState('');
  const [qr, setQr] = useState(null);
  const [singers, setSingers] = useState([]);
  const [queue, setQueue] = useState([]);
  const [board, setBoard] = useState({ mode: 'event', rows: [] });
  const [copied, setCopied] = useState(false);
  const [pointActions, setPointActions] = useState([]);
  const [awardFor, setAwardFor] = useState(null);
  const [customPts, setCustomPts] = useState('');
  const [battles, setBattles] = useState([]);
  const [battleTypes, setBattleTypes] = useState([]);
  const [newBattle, setNewBattle] = useState({ challenger_id: '', opponent_id: '', challenge_type: '' });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadEvent = useCallback(async () => {
    try { setEvent(await p2.event(eventId)); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed to load event'); }
  }, [eventId]);
  useEffect(() => { loadEvent(); }, [loadEvent]);

  // Resolve venue name for the always-visible context bar.
  useEffect(() => {
    if (!event) return;
    p2.venues().then((vs) => setVenueName(vs.find((v) => v.id === event.venue_id)?.name || '')).catch(() => {});
  }, [event]);

  const loadQR = async () => { try { setQr(await p2.eventQR(eventId)); } catch (e) { toast.error(e.response?.data?.detail || 'QR failed'); } };
  const loadSingers = useCallback(async () => { try { setSingers((await p2.singerList(eventId)).singers); } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); } }, [eventId]);
  const loadQueue = useCallback(async () => { try { setQueue(await p2.eventQueue(eventId)); } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); } }, [eventId]);
  const loadEventBoard = async () => { try { setBoard({ mode: 'event', rows: (await p2.eventLeaderboard(eventId)).leaderboard }); } catch (e) { toast.error('Failed'); } };
  const loadSeasonBoard = async () => { try { setBoard({ mode: 'season', rows: (await p2.seasonLeaderboard()).leaderboard }); } catch (e) { toast.error('Failed'); } };
  const loadBattles = useCallback(async () => { try { setBattles(await p2.battles(eventId)); } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); } }, [eventId]);

  useEffect(() => {
    if (tab === 'qr' && !qr) loadQR();
    if (tab === 'singers') loadSingers();
    if (tab === 'queue') loadQueue();
    if (tab === 'leaderboard') loadEventBoard();
    if (tab === 'battles') { loadBattles(); loadSingers(); if (!battleTypes.length) p2.battleTypes(eventId).then(setBattleTypes).catch(() => {}); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  useEffect(() => { if (!pointActions.length) p2.pointActions().then(setPointActions).catch(() => {}); }, [pointActions.length]);

  const checkinUrl = qr ? `${FRONTEND_URL}${qr.checkin_path}` : '';
  const copy = () => { navigator.clipboard.writeText(checkinUrl); setCopied(true); toast.success('Check-in URL copied'); setTimeout(() => setCopied(false), 1500); };

  const currentSong = useMemo(() => queue.find((q) => q.status === 'current'), [queue]);
  const pending = useMemo(() => queue.filter((q) => q.status === 'pending'), [queue]);

  const qCtl = async (fn, ...args) => { try { const r = await fn(...args); if (r?.message) toast.success(r.message); loadQueue(); } catch (e) { toast.error(e.response?.data?.detail || 'Action failed'); loadQueue(); } };

  const handleDragEnd = async (evt) => {
    const { active, over } = evt;
    if (!over || active.id === over.id) return;
    const oldIndex = pending.findIndex((i) => i.id === active.id);
    const newIndex = pending.findIndex((i) => i.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    const dragged = pending[oldIndex];
    if (dragged.perk_protected && dragged.position <= 4) { toast.error('This song used a perk and cannot be moved'); return; }
    const reordered = arrayMove(pending, oldIndex, newIndex).map((it, i) => ({ ...it, position: i + 1 }));
    setQueue((prev) => { const cur = prev.find((i) => i.status === 'current'); return cur ? [cur, ...reordered] : reordered; });
    try { await p2.reorderQueue(eventId, active.id, newIndex + 1); toast.success(`Moved to #${newIndex + 1}`); loadQueue(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed to reorder'); loadQueue(); }
  };

  const doAward = async (points, action_id, notes) => {
    if (!awardFor) return;
    if (!points || points <= 0) { toast.error('Enter a positive amount'); return; }
    try {
      await p2.awardPoints(eventId, { user_id: awardFor.user_id, points, action_id, notes });
      toast.success(`Awarded ${points} pts to ${awardFor.display_name}`);
      setAwardFor(null); setCustomPts('');
      loadSingers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Award failed'); }
  };

  const bCtl = async (fn, ...args) => { try { const r = await fn(...args); if (r?.message) toast.success(r.message); loadBattles(); } catch (e) { toast.error(e.response?.data?.detail || 'Action failed'); } };
  const createBattle = async () => {
    if (!newBattle.challenger_id || !newBattle.opponent_id || !newBattle.challenge_type) { toast.error('Pick both singers and a battle type'); return; }
    try { await p2.createBattle(eventId, newBattle); toast.success('Battle created'); setNewBattle({ challenger_id: '', opponent_id: '', challenge_type: '' }); loadBattles(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed to create battle'); }
  };

  return (
    <Phase2Shell
      title={event ? event.name : 'Event'}
      subtitle={event ? `${event.event_date}` : ''}
      back={event ? `/admin/phase2/venues/${event.venue_id}` : '/admin/phase2'}
      crumbs={[{ label: 'KJ Console', to: '/admin/kj' }, { label: 'Run Show' }, { label: event?.name || '' }]}
      actions={event && <StatusBadge status={event.status} />}
    >
      {/* Always-visible selected-show context */}
      {event && (
        <div className="glass-card p-4 border border-gold/30 mb-6 flex flex-wrap items-center gap-x-6 gap-y-2" data-testid="selected-event-bar">
          <div className="flex items-center gap-2"><Users className="w-4 h-4 text-gold" /><span className="text-white/50 text-sm">Venue:</span><span className="text-white font-medium">{venueName || event.venue_id}</span></div>
          <div className="flex items-center gap-2"><Mic2 className="w-4 h-4 text-gold" /><span className="text-white/50 text-sm">Show:</span><span className="text-gold font-cinzel">{event.name}</span></div>
          <div className="flex items-center gap-2"><span className="text-white/50 text-sm">Status:</span><StatusBadge status={event.status} /></div>
        </div>
      )}

      <div className="flex gap-2 flex-wrap mb-6 border-b border-white/10 pb-3" data-testid="event-tabs">
        {TABS.map((t) => (
          <button key={t.k} data-testid={`tab-${t.k}`} onClick={() => setTab(t.k)}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition ${tab === t.k ? 'bg-gold text-black font-semibold' : 'text-white/60 hover:text-gold border border-white/10'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW */}
      {tab === 'overview' && event && (
        <div className="glass-card p-6 border border-white/10 space-y-3" data-testid="event-overview">
          {[['Event', event.name], ['Date', event.event_date], ['Status', event.status], ['Venue', venueName || event.venue_id], ['Location ID', event.location_id], ['Event ID', event.id]].map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-white/5 pb-2">
              <span className="text-white/50">{k}</span><span className="text-white/90 font-mono text-sm">{v}</span>
            </div>
          ))}
        </div>
      )}

      {/* QR */}
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

      {/* SINGERS */}
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
                  <td className="px-2" data-testid={`singer-points-${s.user_id}`}>{s.event_points}</td>
                  <td className="px-2">{s.songs_performed}</td>
                  <td className="px-2 text-right"><button data-testid={`award-${s.user_id}`} onClick={() => setAwardFor(s)} className="text-gold hover:brightness-110 inline-flex items-center gap-1"><Award className="w-4 h-4" /> Award</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* QUEUE */}
      {tab === 'queue' && (
        <div className="space-y-6" data-testid="queue-panel">
          {currentSong && (
            <div className="glass-card p-6 border-gold/30" data-testid="now-performing">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm font-medium text-green-400 uppercase tracking-wider">Now Performing</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="p-3 bg-gold/10 rounded-xl shrink-0"><Mic2 className="w-6 h-6 text-gold" /></div>
                  <div className="min-w-0">
                    <h3 className="font-cinzel font-bold text-xl text-white truncate">{currentSong.user_name}</h3>
                    <p className="text-gold truncate">{currentSong.song_title} — {currentSong.artist}</p>
                    {currentSong.message_to_admin && (
                      <div className="mt-2 p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                        <p className="text-purple-300 text-xs font-medium mb-1">Message:</p>
                        <p className="text-white/80 text-sm break-words whitespace-pre-wrap">{currentSong.message_to_admin}</p>
                      </div>
                    )}
                  </div>
                </div>
                <button onClick={() => qCtl(p2.completeSong, eventId, currentSong.id)} data-testid="complete-current-btn"
                  className="bg-gold text-black font-semibold px-4 py-2 rounded-full inline-flex items-center gap-2 shrink-0"><Check className="w-4 h-4" /> Complete</button>
              </div>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-cinzel font-bold text-xl text-white">Up Next ({pending.length})</h2>
              <p className="text-white/40 text-sm flex items-center gap-2"><GripVertical className="w-4 h-4" /> Drag to reorder</p>
            </div>
            {pending.length === 0 ? (
              <div className="glass-card p-8 text-center border border-white/10"><Mic2 className="w-10 h-10 text-white/20 mx-auto mb-3" /><p className="text-white/60">Queue is empty</p></div>
            ) : (
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={pending.map((i) => i.id)} strategy={verticalListSortingStrategy}>
                  <div className="space-y-3" data-testid="queue-tbody">
                    {pending.map((item) => (
                      <SortableQueueRow key={item.id} item={item} pendingLen={pending.length}
                        onUp={(id) => qCtl(p2.moveUp, eventId, id)} onDown={(id) => qCtl(p2.moveDown, eventId, id)}
                        onCurrent={(id) => qCtl(p2.setCurrent, eventId, id)} onComplete={(id) => qCtl(p2.completeSong, eventId, id)}
                        onRemove={(id) => qCtl(p2.removeSong, eventId, id)} />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </div>
        </div>
      )}

      {/* BATTLES */}
      {tab === 'battles' && (
        <div className="space-y-6" data-testid="battles-panel">
          <div className="glass-card p-5 border border-white/10" data-testid="create-battle-card">
            <h2 className="font-cinzel text-lg text-gold mb-4 flex items-center gap-2"><Swords className="w-5 h-5" /> Start a Battle</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <select data-testid="battle-challenger-select" value={newBattle.challenger_id} onChange={(e) => setNewBattle((b) => ({ ...b, challenger_id: e.target.value }))} className="royal-input bg-black/40">
                <option value="">Challenger…</option>
                {singers.map((s) => <option key={s.user_id} value={s.user_id}>{s.display_name}</option>)}
              </select>
              <select data-testid="battle-opponent-select" value={newBattle.opponent_id} onChange={(e) => setNewBattle((b) => ({ ...b, opponent_id: e.target.value }))} className="royal-input bg-black/40">
                <option value="">Opponent…</option>
                {singers.map((s) => <option key={s.user_id} value={s.user_id}>{s.display_name}</option>)}
              </select>
              <select data-testid="battle-type-select" value={newBattle.challenge_type} onChange={(e) => setNewBattle((b) => ({ ...b, challenge_type: e.target.value }))} className="royal-input bg-black/40">
                <option value="">Battle type…</option>
                {battleTypes.map((t) => <option key={t.id} value={t.id}>{t.name} (+{t.points_winner}/{t.points_participant})</option>)}
              </select>
              <button data-testid="create-battle-btn" onClick={createBattle} className="bg-gold text-black font-semibold rounded-full px-4 py-2 hover:brightness-110">Create Battle</button>
            </div>
            {singers.length < 2 && <p className="text-white/40 text-xs mt-3">Need at least two checked-in singers to start a battle.</p>}
          </div>

          <div className="space-y-4" data-testid="battles-list">
            {battles.length === 0 && <div className="glass-card p-8 text-center border border-white/10"><Swords className="w-10 h-10 text-white/20 mx-auto mb-3" /><p className="text-white/60">No battles in this event yet.</p></div>}
            {battles.map((b) => (
              <div key={b.id} data-testid={`battle-${b.id}`} className={`glass-card p-5 border ${b.voting_open ? 'border-green-500/50' : 'border-white/10'}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-gold/10 rounded-xl"><Swords className="w-5 h-5 text-gold" /></div>
                    <div>
                      <p className="text-white/50 text-xs">{b.type_info?.name}</p>
                      <h3 className="font-cinzel font-bold text-white">{b.challenger_name} <span className="text-gold">vs</span> {b.opponent_name}</h3>
                    </div>
                  </div>
                  <div className="text-right">
                    <StatusBadge status={b.status} />
                    <p className="text-white/50 text-xs mt-1">Votes: <span className="text-gold" data-testid={`battle-votes-${b.id}`}>{b.votes_challenger} – {b.votes_opponent}</span></p>
                  </div>
                </div>

                {b.status === 'completed' ? (
                  <div className="flex items-center gap-2 text-gold" data-testid={`battle-winner-${b.id}`}><Crown className="w-4 h-4" /> Winner: <span className="font-semibold">{b.winner_name}</span></div>
                ) : b.status === 'cancelled' ? (
                  <p className="text-white/40 text-sm">Battle cancelled.</p>
                ) : (
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap gap-2">
                      {!b.voting_open ? (
                        <button data-testid={`battle-open-${b.id}`} onClick={() => bCtl(p2.openBattleVoting, eventId, b.id)} className="flex-1 min-w-[140px] bg-green-600 hover:bg-green-700 text-white rounded-lg px-3 py-2 inline-flex items-center justify-center gap-2"><Vote className="w-4 h-4" /> Open Voting</button>
                      ) : (
                        <button data-testid={`battle-close-${b.id}`} onClick={() => bCtl(p2.closeBattleVoting, eventId, b.id)} className="flex-1 min-w-[140px] bg-orange-600 hover:bg-orange-700 text-white rounded-lg px-3 py-2 inline-flex items-center justify-center gap-2"><XCircle className="w-4 h-4" /> Close Voting</button>
                      )}
                      <button data-testid={`battle-finalize-${b.id}`} onClick={() => bCtl(p2.finalizeBattle, eventId, b.id)} disabled={(b.vote_count || 0) === 0}
                        className="flex-1 min-w-[140px] bg-gold text-black font-semibold rounded-lg px-3 py-2 inline-flex items-center justify-center gap-2 disabled:opacity-40"><Trophy className="w-4 h-4" /> Finalize (Votes)</button>
                      <button data-testid={`battle-cancel-${b.id}`} onClick={() => bCtl(p2.cancelBattle, eventId, b.id)} className="border border-red-500/40 text-red-400 rounded-lg px-3 py-2 hover:bg-red-500/10">Cancel</button>
                    </div>
                    <div className="border-t border-white/10 pt-3">
                      <p className="text-white/50 text-xs mb-2 text-center">Pick winner (no votes required)</p>
                      <div className="flex gap-2">
                        <button data-testid={`battle-pick-challenger-${b.id}`} onClick={() => bCtl(p2.pickBattleWinner, eventId, b.id, b.challenger_id)} className="flex-1 border border-blue-500/50 text-blue-400 rounded-lg px-3 py-2 hover:bg-blue-500/10 inline-flex items-center justify-center gap-1"><Crown className="w-4 h-4" /> {b.challenger_name} Wins</button>
                        <button data-testid={`battle-pick-opponent-${b.id}`} onClick={() => bCtl(p2.pickBattleWinner, eventId, b.id, b.opponent_id)} className="flex-1 border border-purple-500/50 text-purple-400 rounded-lg px-3 py-2 hover:bg-purple-500/10 inline-flex items-center justify-center gap-1"><Crown className="w-4 h-4" /> {b.opponent_name} Wins</button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LEADERBOARD */}
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

      {/* AWARD DIALOG (Phase 1 point rules + custom, attributed to this event/season) */}
      <Dialog open={!!awardFor} onOpenChange={(o) => { if (!o) { setAwardFor(null); setCustomPts(''); } }}>
        <DialogContent className="bg-royal-paper border-white/10 text-white max-w-md max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-cinzel text-2xl text-gold flex items-center gap-2"><Gift className="w-5 h-5" /> Award Points{awardFor ? ` — ${awardFor.display_name}` : ''}</DialogTitle>
          </DialogHeader>
          <p className="text-white/50 text-sm">Awards go to this singer for <span className="text-gold">{event?.name}</span> and the current season.</p>
          <div className="space-y-2 mt-3" data-testid="award-actions">
            {pointActions.map((a) => (
              <button key={a.id} data-testid={`award-action-${a.id}`} onClick={() => doAward(a.points, a.id, a.name)}
                className="w-full flex items-center justify-between p-3 bg-white/5 hover:bg-gold/10 rounded-lg text-left">
                <div><p className="text-white font-medium">{a.name}</p><p className="text-white/50 text-xs">{a.description}</p></div>
                <span className={`font-cinzel font-bold ${a.points >= 100 ? 'text-gold' : a.points >= 50 ? 'text-purple-400' : 'text-white'}`}>+{a.points}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 border-t border-white/10 pt-4">
            <label className="block text-sm text-white/70 mb-2">Custom amount</label>
            <div className="flex gap-2">
              <input data-testid="custom-points-input" type="number" min="1" value={customPts} onChange={(e) => setCustomPts(e.target.value)} placeholder="e.g. 15" className="royal-input flex-1 bg-black/40" />
              <button data-testid="award-custom-btn" onClick={() => doAward(parseInt(customPts, 10), 'custom_award', 'Custom award')} className="bg-gold text-black font-semibold rounded-lg px-4">Award</button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Phase2Shell>
  );
};

export default EventManagePage;
