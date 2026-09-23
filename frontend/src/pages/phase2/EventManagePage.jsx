import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Mic2, Users, Gift, Swords, Trophy, QrCode, ChevronUp, ChevronDown, Play, XCircle,
  CheckCircle, GripVertical, Lock, RefreshCw, Copy, Check, Search, Vote, Crown, Award,
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
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { p2, qrImage, FRONTEND_URL } from '@/lib/phase2Api';

// ---- Sortable pending-queue row (mirrors old Admin/KJ panel) ----------------
const SortableQueueItem = ({ item, pendingLen, onSetCurrent, onRemove, onMoveUp, onMoveDown }) => {
  const locked = item.perk_protected && item.position <= 4;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.id, disabled: locked });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1, zIndex: isDragging ? 1000 : 1 };
  return (
    <div ref={setNodeRef} style={style} data-testid={`admin-queue-item-${item.id}`}
      className={`glass-card p-4 ${item.perk_protected ? 'border-gold/40' : ''} ${isDragging ? 'shadow-lg shadow-gold/20' : ''}`}>
      <div className="flex items-center gap-4">
        <div {...attributes} {...listeners}
          className={`cursor-grab active:cursor-grabbing p-1 rounded ${locked ? 'opacity-30 cursor-not-allowed' : 'hover:bg-white/10'}`}
          title={locked ? 'Perk protected - cannot be moved' : 'Drag to reorder'} data-testid={`q-drag-${item.id}`}>
          <GripVertical className="w-5 h-5 text-white/50" />
        </div>
        <div className="relative">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${item.perk_protected ? 'bg-gold/20' : 'bg-white/5'}`}>
            <span className="font-cinzel font-bold text-gold">{item.position}</span>
          </div>
          {item.perk_protected && (
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-gold rounded-full flex items-center justify-center" title="Perk Protected">
              <Lock className="w-2.5 h-2.5 text-purple-deep" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-white truncate">{item.user_name}</h3>
            {item.perk_protected && <span className="text-xs bg-gold/20 text-gold px-1.5 py-0.5 rounded shrink-0">Perk Used</span>}
          </div>
          <p className="text-gold text-sm truncate">{item.song_title} - {item.artist}</p>
          {item.message_to_admin && (
            <div className="mt-2 p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg max-w-full overflow-hidden" data-testid={`q-msg-${item.id}`}>
              <p className="text-purple-300 text-xs font-medium mb-1">Message from singer:</p>
              <p className="text-white/80 text-sm break-words whitespace-pre-wrap">{item.message_to_admin}</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex flex-col gap-1">
            <Button size="sm" variant="outline" onClick={() => onMoveUp(item.id)} disabled={item.position === 1 || locked}
              data-testid={`move-up-${item.id}`} className="h-6 w-6 p-0 border-white/20 text-white hover:bg-white/10 disabled:opacity-30" title="Move up">
              <ChevronUp className="w-4 h-4" />
            </Button>
            <Button size="sm" variant="outline" onClick={() => onMoveDown(item.id)} disabled={item.position === pendingLen || locked}
              data-testid={`move-down-${item.id}`} className="h-6 w-6 p-0 border-white/20 text-white hover:bg-white/10 disabled:opacity-30" title="Move down">
              <ChevronDown className="w-4 h-4" />
            </Button>
          </div>
          <Button size="sm" onClick={() => onSetCurrent(item.id)} data-testid={`set-current-${item.id}`} className="bg-green-600 hover:bg-green-700 text-white" title="Set as Now Performing">
            <Play className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="destructive" onClick={() => onRemove(item.id)} data-testid={`remove-${item.id}`} title="Remove from queue">
            <XCircle className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

const EventManagePage = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [venueName, setVenueName] = useState('');
  const [queue, setQueue] = useState([]);
  const [singers, setSingers] = useState([]);
  const [pointActions, setPointActions] = useState([]);
  const [battles, setBattles] = useState([]);
  const [battleTypes, setBattleTypes] = useState([]);
  const [board, setBoard] = useState({ mode: 'event', rows: [] });
  const [qr, setQr] = useState(null);
  const [activeTab, setActiveTab] = useState('queue');
  const qrReqRef = useRef(0);   // guards against stale async QR responses on rapid event switches
  const [copied, setCopied] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [awardFor, setAwardFor] = useState(null);
  const [customPts, setCustomPts] = useState('');
  const [awarding, setAwarding] = useState(false);   // in-flight guard: blocks double-clicks
  const [awardKey, setAwardKey] = useState(null);     // per-dialog-open idempotency key
  const [newBattle, setNewBattle] = useState({ challenger_id: '', opponent_id: '', challenge_type: '' });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadEvent = useCallback(async () => {
    try { setEvent(await p2.event(eventId)); }
    catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load event');
      if (e.response?.status === 403) navigate('/admin/kj');
    }
  }, [eventId, navigate]);
  const loadQueue = useCallback(async () => { try { setQueue(await p2.eventQueue(eventId)); } catch (e) { toast.error(e.response?.data?.detail || 'Failed to load queue'); } }, [eventId]);
  const loadSingers = useCallback(async () => { try { setSingers((await p2.singerList(eventId)).singers); } catch (e) {} }, [eventId]);
  const loadBattles = useCallback(async () => { try { setBattles(await p2.battles(eventId)); } catch (e) {} }, [eventId]);
  const loadEventBoard = async () => { try { setBoard({ mode: 'event', rows: (await p2.eventLeaderboard(eventId)).leaderboard }); } catch (e) {} };
  const loadSeasonBoard = async () => { try { setBoard({ mode: 'season', rows: (await p2.seasonLeaderboard()).leaderboard }); } catch (e) {} };
  const loadQR = async () => {
    // Capture the event this request belongs to; ignore the response if the KJ has since
    // switched events (prevents a slow response for event A overwriting event B's QR).
    const reqId = ++qrReqRef.current;
    const forEvent = eventId;
    try {
      const data = await p2.eventQR(forEvent);
      if (qrReqRef.current === reqId && forEvent === eventId) setQr(data);
    } catch (e) {
      if (qrReqRef.current === reqId && forEvent === eventId) toast.error(e.response?.data?.detail || 'QR failed');
    }
  };

  useEffect(() => { loadEvent(); loadQueue(); loadSingers(); loadBattles(); }, [loadEvent, loadQueue, loadSingers, loadBattles]);
  // QR belongs to a specific event: the instant the selected event changes, drop any previously
  // displayed QR so a stale code from another event can never be shown/used. Invalidate in-flight
  // QR requests too. Fresh QR is (re)loaded when the QR tab is open for the current event.
  useEffect(() => { qrReqRef.current++; setQr(null); }, [eventId]);
  useEffect(() => {
    if (activeTab === 'qr' && event && !qr) loadQR();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, eventId, event]);
  // Near-real-time KJ notification of pending battle requests (polling; App already polls elsewhere).
  useEffect(() => {
    const id = setInterval(() => { loadBattles(); }, 12000);
    return () => clearInterval(id);
  }, [loadBattles]);
  useEffect(() => { p2.pointActions().then(setPointActions).catch(() => {}); p2.battleTypes(eventId).then(setBattleTypes).catch(() => {}); }, [eventId]);
  useEffect(() => { if (event) p2.venues().then((vs) => setVenueName(vs.find((v) => v.id === event.venue_id)?.name || '')).catch(() => {}); }, [event]);

  const currentSong = useMemo(() => queue.find((q) => q.status === 'current'), [queue]);
  const pending = useMemo(() => queue.filter((q) => q.status === 'pending'), [queue]);
  const songsDone = useMemo(() => singers.reduce((n, s) => n + (s.songs_performed || 0), 0), [singers]);
  const activeBattles = useMemo(() => battles.filter((b) => b.status === 'pending' || b.status === 'voting'), [battles]);
  const pendingRequests = useMemo(() => battles.filter((b) => b.status === 'pending'), [battles]);

  const checkinUrl = qr ? `${FRONTEND_URL}${qr.checkin_path}` : '';
  const copy = () => { navigator.clipboard.writeText(checkinUrl); setCopied(true); toast.success('Check-in URL copied'); setTimeout(() => setCopied(false), 1500); };

  const qCtl = async (fn, ...args) => { try { const r = await fn(...args); if (r?.message) toast.success(r.message); loadQueue(); loadSingers(); } catch (e) { toast.error(e.response?.data?.detail || 'Action failed'); loadQueue(); } };

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

  // Open the award dialog and mint a fresh idempotency key for THIS award session.
  const openAward = (s) => {
    setAwardKey((typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
    setAwardFor(s);
  };

  const doAward = async (points, action_id, notes) => {
    if (!awardFor) return;
    if (!points || points <= 0) { toast.error('Enter a positive amount'); return; }
    if (awarding) return;   // ignore rapid double-clicks while a request is in flight
    setAwarding(true);
    try {
      // Stable per-(session, action) dedupe key: a double-click/retry of the SAME submission
      // maps to the same key (awarded once); reopening the dialog mints a new key so a
      // separate legitimate award of the same action later is allowed.
      const dedupe_key = `kjaward:${awardKey}:${action_id}:${points}`;
      const r = await p2.awardPoints(eventId, { user_id: awardFor.user_id, points, action_id, notes, dedupe_key });
      toast.success(`Awarded ${points} pts to ${awardFor.display_name}` + (r.season_points != null ? ` (season ${r.season_points})` : ''));
      if (r.badge_names && r.badge_names.length) {
        toast.success(`🏅 Badge unlocked: ${r.badge_names.join(', ')}${r.bonus_points ? ` (+${r.bonus_points} bonus pts)` : ''}`, { duration: 5000 });
      }
      setAwardFor(null); setCustomPts(''); loadSingers();
    } catch (e) {
      if (e.response?.status === 409) {
        // Duplicate of this exact submission — already applied, so this is NOT a new award.
        toast.info('That award was already applied — not awarded again.');
        setAwardFor(null); setCustomPts(''); loadSingers();
      } else {
        toast.error(e.response?.data?.detail || 'Award failed');
      }
    } finally { setAwarding(false); }
  };

  const bCtl = async (fn, ...args) => { try { const r = await fn(...args); if (r?.message) toast.success(r.message); loadBattles(); loadSingers(); } catch (e) { toast.error(e.response?.data?.detail || 'Action failed'); } };
  const createBattle = async () => {
    if (!newBattle.challenger_id || !newBattle.opponent_id || !newBattle.challenge_type) { toast.error('Pick both singers and a battle type'); return; }
    if (newBattle.challenger_id === newBattle.opponent_id) { toast.error('Pick two different singers'); return; }
    try { await p2.createBattle(eventId, newBattle); toast.success('Battle created'); setNewBattle({ challenger_id: '', opponent_id: '', challenge_type: '' }); loadBattles(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed to create battle'); }
  };

  const filteredSingers = singers.filter((s) => s.display_name?.toLowerCase().includes(userSearch.toLowerCase()));

  return (
    <Phase2Shell
      title="KJ Show Console"
      back={event ? `/admin/kj` : '/admin/kj'}
      crumbs={[{ label: 'KJ Console', to: '/admin/kj' }, { label: 'Run Show' }, { label: event?.name || '' }]}
      actions={event && <StatusBadge status={event.status} />}
    >
      {/* Selected-event context (central) */}
      {event && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 border border-gold/30 mb-6 flex flex-wrap items-center gap-x-6 gap-y-2" data-testid="selected-event-bar">
          <div className="flex items-center gap-2"><Users className="w-4 h-4 text-gold" /><span className="text-white/50 text-sm">Venue:</span><span className="text-white font-medium">{venueName || event.venue_id}</span></div>
          <div className="flex items-center gap-2"><Mic2 className="w-4 h-4 text-gold" /><span className="text-white/50 text-sm">Show:</span><span className="text-gold font-cinzel text-lg">{event.name}</span></div>
          <div className="flex items-center gap-2"><span className="text-white/50 text-sm">Date:</span><span className="text-white/80">{event.event_date}</span></div>
          <div className="flex items-center gap-2"><span className="text-white/50 text-sm">Status:</span><StatusBadge status={event.status} /></div>
        </motion.div>
      )}

      {/* Stats overview (mirrors old Admin panel) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6" data-testid="kj-stats">
        <div className="stat-card"><div className="stat-value">{singers.length}</div><div className="stat-label">Checked-In</div></div>
        <div className="stat-card"><div className="stat-value">{songsDone}</div><div className="stat-label">Songs Done</div></div>
        <div className="stat-card"><div className="stat-value">{pending.length + (currentSong ? 1 : 0)}</div><div className="stat-label">In Queue</div></div>
        <div className="stat-card"><div className="stat-value">{activeBattles.length}</div><div className="stat-label">Active Battles</div></div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="w-full sm:w-auto bg-royal-paper border border-white/10 flex-wrap h-auto">
          <TabsTrigger value="queue" data-testid="tab-queue" className="data-[state=active]:bg-gold/20 data-[state=active]:text-gold"><Mic2 className="w-4 h-4 mr-2" />Queue</TabsTrigger>
          <TabsTrigger value="singers" data-testid="tab-singers" className="data-[state=active]:bg-gold/20 data-[state=active]:text-gold"><Users className="w-4 h-4 mr-2" />Singers</TabsTrigger>
          <TabsTrigger value="award" data-testid="tab-award" className="data-[state=active]:bg-gold/20 data-[state=active]:text-gold"><Gift className="w-4 h-4 mr-2" />Award Points</TabsTrigger>
          <TabsTrigger value="battles" data-testid="tab-battles" className="data-[state=active]:bg-gold/20 data-[state=active]:text-gold relative"><Swords className="w-4 h-4 mr-2" />Battles ({activeBattles.length}){pendingRequests.length > 0 && <span data-testid="battles-pending-dot" className="ml-1 w-2 h-2 bg-green-400 rounded-full animate-pulse" />}</TabsTrigger>
          <TabsTrigger value="leaderboard" data-testid="tab-leaderboard" className="data-[state=active]:bg-gold/20 data-[state=active]:text-gold"><Trophy className="w-4 h-4 mr-2" />Leaderboard</TabsTrigger>
          <TabsTrigger value="qr" data-testid="tab-qr" className="data-[state=active]:bg-gold/20 data-[state=active]:text-gold"><QrCode className="w-4 h-4 mr-2" />QR Check-In</TabsTrigger>
        </TabsList>

        {/* QUEUE */}
        <TabsContent value="queue" className="mt-6 space-y-6">
          {currentSong && (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="glass-card p-6 border-gold/30" data-testid="now-performing">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm font-medium text-green-400 uppercase tracking-wider">Now Performing</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="p-3 bg-gold/10 rounded-xl shrink-0"><Mic2 className="w-6 h-6 text-gold" /></div>
                  <div className="min-w-0 overflow-hidden">
                    <h3 className="font-cinzel font-bold text-xl text-white truncate">{currentSong.user_name}</h3>
                    <p className="text-gold truncate">{currentSong.song_title} - {currentSong.artist}</p>
                    {currentSong.message_to_admin && (
                      <div className="mt-2 p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg max-w-full overflow-hidden">
                        <p className="text-purple-300 text-xs font-medium mb-1">Message:</p>
                        <p className="text-white/80 text-sm break-words whitespace-pre-wrap">{currentSong.message_to_admin}</p>
                      </div>
                    )}
                  </div>
                </div>
                <Button onClick={() => qCtl(p2.completeSong, eventId, currentSong.id)} data-testid="complete-song-btn" className="btn-gold shrink-0">
                  <CheckCircle className="w-4 h-4 mr-2" /> Complete
                </Button>
              </div>
            </motion.div>
          )}

          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-cinzel font-bold text-xl text-white">Up Next ({pending.length})</h2>
              <p className="text-white/40 text-sm flex items-center gap-2"><GripVertical className="w-4 h-4" /> Drag to reorder</p>
            </div>
            {pending.length === 0 ? (
              <div className="glass-card p-8 text-center"><Mic2 className="w-10 h-10 text-white/20 mx-auto mb-3" /><p className="text-white/60">Queue is empty</p></div>
            ) : (
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={pending.map((i) => i.id)} strategy={verticalListSortingStrategy}>
                  <div className="space-y-3" data-testid="queue-tbody">
                    {pending.map((item) => (
                      <SortableQueueItem key={item.id} item={item} pendingLen={pending.length}
                        onSetCurrent={(id) => qCtl(p2.setCurrent, eventId, id)}
                        onRemove={(id) => qCtl(p2.removeSong, eventId, id)}
                        onMoveUp={(id) => qCtl(p2.moveUp, eventId, id)}
                        onMoveDown={(id) => qCtl(p2.moveDown, eventId, id)} />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </div>
        </TabsContent>

        {/* SINGERS */}
        <TabsContent value="singers" className="mt-6">
          <div className="glass-card overflow-hidden" data-testid="singers-panel">
            <div className="p-4 border-b border-white/10"><h2 className="font-cinzel font-bold text-lg text-white">Checked-In Singers ({singers.length})</h2></div>
            <div className="divide-y divide-white/5 max-h-[600px] overflow-y-auto">
              {singers.length === 0 && <p className="text-white/40 p-4">No singers checked in yet.</p>}
              {singers.map((s) => (
                <div key={s.user_id} className="flex items-center gap-4 p-4" data-testid={`singer-row-${s.user_id}`}>
                  <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center font-cinzel text-gold">{s.list_position}</div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-white truncate">{s.display_name}</h3>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-gold text-sm" data-testid={`singer-points-${s.user_id}`}>{s.event_points} event pts</span>
                      <span className="text-white/40 text-xs">{s.songs_performed} songs</span>
                      <StatusBadge status={s.status} />
                    </div>
                  </div>
                  <Button size="sm" className="btn-gold" data-testid={`award-${s.user_id}`} onClick={() => openAward(s)}><Award className="w-4 h-4 mr-2" /> Award</Button>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        {/* AWARD POINTS (dedicated tab, mirrors old panel) */}
        <TabsContent value="award" className="mt-6 space-y-6">
          <div className="glass-card p-4">
            <label className="block text-sm font-medium text-white/80 mb-2">Search Singer to Award Points</label>
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input value={userSearch} onChange={(e) => setUserSearch(e.target.value)} placeholder="Search checked-in singers..."
                data-testid="award-search-input" className="w-full royal-input pl-12" />
            </div>
          </div>
          <div className="glass-card overflow-hidden">
            <div className="p-4 border-b border-white/10 bg-gold/5"><h2 className="font-cinzel font-bold text-lg text-gold">Select Singer to Award Points</h2></div>
            <div className="divide-y divide-white/5 max-h-[400px] overflow-y-auto">
              {filteredSingers.length === 0 && <p className="text-white/40 p-4">No checked-in singers match.</p>}
              {filteredSingers.map((s) => (
                <div key={s.user_id} className="flex items-center justify-between p-4 hover:bg-white/5 cursor-pointer" onClick={() => openAward(s)} data-testid={`award-user-${s.user_id}`}>
                  <div><h3 className="font-medium text-white">{s.display_name}</h3><p className="text-white/40 text-sm">{s.event_points} event pts</p></div>
                  <Button size="sm" className="btn-gold"><Gift className="w-4 h-4 mr-2" /> Award</Button>
                </div>
              ))}
            </div>
          </div>
          <div className="glass-card overflow-hidden">
            <div className="p-4 border-b border-white/10"><h2 className="font-cinzel font-bold text-lg text-white">Point Actions Reference</h2></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-white/5">
              {pointActions.map((a) => (
                <div key={a.id} className="p-4 bg-royal-paper flex items-center justify-between">
                  <span className="text-white">{a.name}</span>
                  <span className={`font-bold ${a.points >= 100 ? 'text-gold' : a.points >= 50 ? 'text-purple-400' : 'text-white/80'}`}>+{a.points}</span>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        {/* BATTLES */}
        <TabsContent value="battles" className="mt-6 space-y-6" data-testid="battles-panel">
          {pendingRequests.length > 0 && (
            <div className="glass-card p-4 border border-green-500/40 flex items-center gap-3" data-testid="pending-battles-banner">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
              <span className="text-green-300 text-sm font-medium">
                {pendingRequests.length} battle{pendingRequests.length > 1 ? 's' : ''} pending — start voting or pick a winner below.
              </span>
            </div>
          )}
          <div className="glass-card p-5" data-testid="create-battle-card">
            <h2 className="font-cinzel text-lg text-gold mb-4 flex items-center gap-2"><Swords className="w-5 h-5" /> Start a Battle</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <select data-testid="battle-challenger-select" value={newBattle.challenger_id} onChange={(e) => setNewBattle((b) => ({ ...b, challenger_id: e.target.value }))} className="royal-input bg-black/40">
                <option value="">Challenger…</option>{singers.map((s) => <option key={s.user_id} value={s.user_id}>{s.display_name}</option>)}
              </select>
              <select data-testid="battle-opponent-select" value={newBattle.opponent_id} onChange={(e) => setNewBattle((b) => ({ ...b, opponent_id: e.target.value }))} className="royal-input bg-black/40">
                <option value="">Opponent…</option>{singers.map((s) => <option key={s.user_id} value={s.user_id}>{s.display_name}</option>)}
              </select>
              <select data-testid="battle-type-select" value={newBattle.challenge_type} onChange={(e) => setNewBattle((b) => ({ ...b, challenge_type: e.target.value }))} className="royal-input bg-black/40">
                <option value="">Battle type…</option>{battleTypes.map((t) => <option key={t.id} value={t.id}>{t.name} (+{t.points_winner}/{t.points_participant})</option>)}
              </select>
              <Button data-testid="create-battle-btn" onClick={createBattle} className="btn-gold">Create Battle</Button>
            </div>
            {singers.length < 2 && <p className="text-white/40 text-xs mt-3">Need at least two checked-in singers to start a battle.</p>}
          </div>
          <div className="space-y-4" data-testid="battles-list">
            {battles.length === 0 && <div className="glass-card p-12 text-center"><Swords className="w-12 h-12 text-white/20 mx-auto mb-4" /><p className="text-white/60 text-lg">No battles yet</p></div>}
            {battles.map((b) => (
              <motion.div key={b.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid={`battle-${b.id}`}
                className={`glass-card p-6 ${b.voting_open ? 'border-green-500/50' : 'border-white/10'}`}>
                {b.voting_open && <div className="flex items-center gap-2 mb-4"><div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" /><span className="text-sm font-medium text-green-400 uppercase tracking-wider">Voting Open</span></div>}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-gold/10 rounded-xl"><Swords className="w-6 h-6 text-gold" /></div>
                    <div><p className="text-white/60 text-sm">{b.type_info?.name}{b.source === 'singer_request' && <span className="ml-2 text-green-400" data-testid={`battle-source-${b.id}`}>• Requested by singer</span>}</p>
                      <h3 className="font-cinzel font-bold text-lg text-white">{b.challenger_name} <span className="text-gold">vs</span> {b.opponent_name}</h3></div>
                  </div>
                  <div className="text-right"><p className="text-white/60 text-sm">Votes</p><p className="text-gold font-bold text-xl" data-testid={`battle-votes-${b.id}`}>{b.votes_challenger} – {b.votes_opponent}</p></div>
                </div>
                {b.status === 'completed' ? (
                  <div className="flex items-center gap-2 text-gold" data-testid={`battle-winner-${b.id}`}><Crown className="w-4 h-4" /> Winner: <span className="font-semibold">{b.winner_name}</span></div>
                ) : b.status === 'cancelled' ? (
                  <p className="text-white/40 text-sm">Battle cancelled.</p>
                ) : (
                  <div className="flex flex-col gap-3">
                    <div className="flex gap-3 flex-wrap">
                      {!b.voting_open ? (
                        <Button onClick={() => bCtl(p2.openBattleVoting, eventId, b.id)} data-testid={`battle-open-${b.id}`} className="flex-1 min-w-[140px] bg-green-600 hover:bg-green-700"><Vote className="w-4 h-4 mr-2" />Open Voting</Button>
                      ) : (
                        <Button onClick={() => bCtl(p2.closeBattleVoting, eventId, b.id)} data-testid={`battle-close-${b.id}`} className="flex-1 min-w-[140px] bg-orange-600 hover:bg-orange-700"><XCircle className="w-4 h-4 mr-2" />Close Voting</Button>
                      )}
                      <Button onClick={() => bCtl(p2.finalizeBattle, eventId, b.id)} data-testid={`battle-finalize-${b.id}`} disabled={(b.vote_count || 0) === 0} className="flex-1 min-w-[140px] btn-gold"><Trophy className="w-4 h-4 mr-2" />Finalize (By Votes)</Button>
                      <Button onClick={() => bCtl(p2.cancelBattle, eventId, b.id)} variant="outline" data-testid={`battle-cancel-${b.id}`} className="border-red-500/40 text-red-400 hover:bg-red-500/10">Cancel</Button>
                    </div>
                    <div className="border-t border-white/10 pt-3">
                      <p className="text-white/50 text-xs mb-2 text-center">Pick Winner (No Votes Required)</p>
                      <div className="flex gap-2">
                        <Button onClick={() => bCtl(p2.pickBattleWinner, eventId, b.id, b.challenger_id)} variant="outline" data-testid={`battle-pick-challenger-${b.id}`} className="flex-1 border-blue-500/50 text-blue-400 hover:bg-blue-500/20"><Crown className="w-4 h-4 mr-1" />{b.challenger_name} Wins</Button>
                        <Button onClick={() => bCtl(p2.pickBattleWinner, eventId, b.id, b.opponent_id)} variant="outline" data-testid={`battle-pick-opponent-${b.id}`} className="flex-1 border-purple-500/50 text-purple-400 hover:bg-purple-500/20"><Crown className="w-4 h-4 mr-1" />{b.opponent_name} Wins</Button>
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </TabsContent>

        {/* LEADERBOARD */}
        <TabsContent value="leaderboard" className="mt-6">
          <div className="glass-card p-4" data-testid="leaderboard-panel">
            <div className="flex gap-2 mb-4">
              <button data-testid="lb-event-btn" onClick={loadEventBoard} className={`px-3 py-1.5 rounded-full text-sm ${board.mode === 'event' ? 'bg-gold text-black' : 'border border-white/15 text-white/60'}`}>This Event</button>
              <button data-testid="lb-season-btn" onClick={loadSeasonBoard} className={`px-3 py-1.5 rounded-full text-sm ${board.mode === 'season' ? 'bg-gold text-black' : 'border border-white/15 text-white/60'}`}>Current Season</button>
            </div>
            <table className="w-full text-sm">
              <thead><tr className="text-white/50 text-left border-b border-white/10"><th className="py-2 px-2">#</th><th className="px-2">Singer</th><th className="px-2">{board.mode === 'season' ? 'Season Pts' : 'Event Pts'}</th>{board.mode === 'season' && <th className="px-2">Rank</th>}</tr></thead>
              <tbody data-testid="leaderboard-tbody">
                {board.rows.length === 0 && <tr><td colSpan="4" className="text-white/40 py-4 px-2">No entries. Click a board above.</td></tr>}
                {board.rows.map((r) => (
                  <tr key={r.user_id} className="border-b border-white/5" data-testid={`lb-row-${r.user_id}`}>
                    <td className="py-2 px-2 text-gold">{r.position}</td><td className="px-2">{r.display_name}</td>
                    <td className="px-2">{board.mode === 'season' ? r.season_points : r.event_points}</td>{board.mode === 'season' && <td className="px-2 text-white/60">{r.rank}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        {/* QR */}
        <TabsContent value="qr" className="mt-6">
          <div className="glass-card p-6 flex flex-col items-center text-center" data-testid="event-qr-panel">
            <div className="text-white/60 mb-1">Event QR for <span className="text-gold font-semibold" data-testid="qr-event-name">{event?.name}</span></div>
            <div className="text-white/40 text-xs mb-4" data-testid="qr-event-meta">
              {event?.event_date}{event?.status ? <> · <span className="uppercase">{event.status}</span></> : null} · ID {eventId?.slice(0, 8)}
            </div>
            {['ended', 'cancelled', 'archived'].includes((event?.status || '').toLowerCase()) ? (
              <div className="w-full max-w-lg bg-red-500/10 border border-red-500/40 rounded-xl p-6" data-testid="qr-checkin-disabled">
                <XCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
                <p className="text-red-300 font-semibold" data-testid="qr-ended-message">Event {(event?.status || '').toLowerCase()} — check-in disabled</p>
                <p className="text-white/50 text-sm mt-1">Singers cannot check into a {(event?.status || '').toLowerCase()} event. Reopen the event to enable QR check-in.</p>
              </div>
            ) : qr ? (
              <>
                <img src={qrImage(checkinUrl)} alt="Event QR" className="rounded-xl border border-gold/30 bg-[#1A0B2E] p-2" data-testid="event-qr-image" />
                <div className="mt-4 w-full max-w-lg">
                  <div className="flex items-center gap-2 bg-black/40 border border-white/15 rounded-lg px-3 py-2">
                    <span className="text-white/70 text-sm truncate flex-1 text-left" data-testid="event-qr-url">{checkinUrl}</span>
                    <button data-testid="copy-qr-url-btn" onClick={copy} className="text-gold hover:brightness-110">{copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}</button>
                  </div>
                  <p className="text-white/40 text-xs mt-2">Expires: {qr.expires_at ? new Date(qr.expires_at).toLocaleString() : 'n/a'}</p>
                  <Button onClick={loadQR} data-testid="refresh-qr-btn" variant="outline" className="mt-4 border-gold/40 text-gold hover:bg-gold/10"><RefreshCw className="w-4 h-4 mr-2" /> Regenerate QR</Button>
                </div>
              </>
            ) : <Button onClick={loadQR} data-testid="generate-qr-btn" className="btn-gold">Generate Event QR</Button>}
          </div>
        </TabsContent>
      </Tabs>

      {/* AWARD DIALOG (Phase-1 point actions + custom, attributed to event/season) */}
      <Dialog open={!!awardFor} onOpenChange={(o) => { if (!o) { setAwardFor(null); setCustomPts(''); } }}>
        <DialogContent className="bg-royal-paper border-white/10 text-white max-w-md max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-cinzel text-2xl text-gold flex items-center gap-2"><Gift className="w-5 h-5" /> Award Points{awardFor ? ` to ${awardFor.display_name}` : ''}</DialogTitle>
          </DialogHeader>
          <p className="text-white/50 text-sm">Recorded for <span className="text-gold">{event?.name}</span> + current season + the singer's lifetime total (legacy King Klub behavior).</p>
          <div className="space-y-2 mt-3" data-testid="award-actions">
            {pointActions.map((a) => (
              <button key={a.id} data-testid={`award-action-${a.id}`} onClick={() => doAward(a.points, a.id, a.name)} disabled={awarding}
                className="w-full flex items-center justify-between p-4 bg-white/5 hover:bg-gold/10 rounded-lg text-left transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                <div><p className="text-white font-medium">{a.name}</p><p className="text-white/50 text-sm">{a.description}</p></div>
                <span className={`font-cinzel font-bold text-lg ${a.points >= 100 ? 'text-gold' : a.points >= 50 ? 'text-purple-400' : 'text-white'}`}>+{a.points}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 border-t border-white/10 pt-4">
            <label className="block text-sm text-white/70 mb-2">Custom amount</label>
            <div className="flex gap-2">
              <input data-testid="custom-points-input" type="number" min="1" value={customPts} onChange={(e) => setCustomPts(e.target.value)} placeholder="e.g. 15" className="royal-input flex-1 bg-black/40" />
              <Button data-testid="award-custom-btn" disabled={awarding} onClick={() => doAward(parseInt(customPts, 10), 'custom_award', 'Custom award')} className="btn-gold disabled:opacity-50">{awarding ? 'Awarding…' : 'Award'}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Phase2Shell>
  );
};

export default EventManagePage;
