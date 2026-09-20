import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Trophy, Crown, Medal, Star, TrendingUp, Calendar, CalendarDays, AlertTriangle } from 'lucide-react';
import { Layout } from '@/components/Layout';
import { useAuth } from '@/context/AuthContext';
import { getRankName } from '@/utils/rankUtils';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Rank colors support both male and female rank names
const rankColors = {
  Peasant: 'bg-gray-500',
  Squire: 'bg-green-500',
  Lady: 'bg-green-500',
  Knight: 'bg-blue-500',
  Dame: 'bg-blue-500',
  Count: 'bg-purple-500',
  Countess: 'bg-purple-500',
  Duke: 'bg-pink-500',
  Duchess: 'bg-pink-500',
  Prince: 'bg-gradient-to-r from-gold-start to-gold-end',
  Princess: 'bg-gradient-to-r from-gold-start to-gold-end',
};

const isMaxRank = (rankName) => rankName === 'Prince' || rankName === 'Princess';

// Normalize the different Phase 2 endpoint shapes into ONE uniform entry.
const normAlltime = (arr) => (arr || []).map((e, i) => ({
  position: e.position ?? i + 1, uid: e.id, display_name: e.display_name,
  points: e.points ?? 0, rankName: getRankName(e.rank, e.title_preference),
  badges: e.badges || [], songs_performed: e.songs_performed,
}));
const normSeason = (arr) => (arr || []).map((e, i) => ({
  position: e.position ?? i + 1, uid: e.user_id, display_name: e.display_name,
  points: e.season_points ?? 0, rankName: e.rank || '', badges: [], songs_performed: null,
}));
const normEvent = (arr) => (arr || []).map((e, i) => ({
  position: e.position ?? i + 1, uid: e.user_id, display_name: e.display_name,
  points: e.event_points ?? 0, rankName: '', badges: [], songs_performed: null,
}));

const LeaderboardPage = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('season');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ season: [], event: [], alltime: [] });
  const [errors, setErrors] = useState({ season: null, event: null, alltime: null });
  const [eventName, setEventName] = useState(null);
  const [seasonName, setSeasonName] = useState('Current Season');
  const [noActiveEvent, setNoActiveEvent] = useState(false);

  const fetchLeaderboards = useCallback(async () => {
    // Each leaderboard is fetched INDEPENDENTLY (Promise.allSettled): a 403/404/500 from one
    // source can never blank the others. No dependency on the retired /leaderboard/tonight.
    const seasonP = axios.get(`${API}/seasons/current/leaderboard`);
    const alltimeP = axios.get(`${API}/leaderboard`);
    const eventP = (async () => {
      const me = await axios.get(`${API}/me/active-event`);
      const ev = me.data.active_event;
      if (!ev) return { _noEvent: true };
      const lb = await axios.get(`${API}/events/${ev.id}/leaderboard`);
      return { _name: ev.name, data: lb.data };
    })();

    const [sRes, aRes, eRes] = await Promise.allSettled([seasonP, alltimeP, eventP]);

    if (sRes.status === 'fulfilled') {
      setData((d) => ({ ...d, season: normSeason(sRes.value.data.leaderboard) }));
      setSeasonName(sRes.value.data.season_year ? `${sRes.value.data.season_year} Season` : 'Current Season');
      setErrors((er) => ({ ...er, season: null }));
    } else {
      setErrors((er) => ({ ...er, season: 'Could not load the season leaderboard.' }));
    }

    if (aRes.status === 'fulfilled') {
      setData((d) => ({ ...d, alltime: normAlltime(aRes.value.data) }));
      setErrors((er) => ({ ...er, alltime: null }));
    } else {
      setErrors((er) => ({ ...er, alltime: 'Could not load the all-time leaderboard.' }));
    }

    if (eRes.status === 'fulfilled') {
      if (eRes.value._noEvent) {
        setNoActiveEvent(true); setEventName(null); setData((d) => ({ ...d, event: [] }));
      } else {
        setNoActiveEvent(false); setEventName(eRes.value._name);
        setData((d) => ({ ...d, event: normEvent(eRes.value.data.leaderboard) }));
      }
      setErrors((er) => ({ ...er, event: null }));
    } else {
      setErrors((er) => ({ ...er, event: 'Could not load the event leaderboard.' }));
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    fetchLeaderboards();
    const h = () => fetchLeaderboards();
    window.addEventListener('pointsUpdated', h);
    window.addEventListener('leaderboardReset', h);
    return () => {
      window.removeEventListener('pointsUpdated', h);
      window.removeEventListener('leaderboardReset', h);
    };
  }, [fetchLeaderboards]);

  const currentLeaderboard = data[activeTab] || [];
  const currentError = errors[activeTab];
  const userPosition = currentLeaderboard.findIndex((e) => e.uid === user?.id) + 1;
  const positionLabel = activeTab === 'event' ? "Event" : activeTab === 'season' ? 'Season' : 'All-Time';

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-gold animate-pulse font-cinzel text-2xl">Loading leaderboard...</div>
        </div>
      </Layout>
    );
  }

  const renderPodium = (leaderboard) => {
    if (leaderboard.length < 3) return null;
    const spots = [
      { i: 1, order: 'order-1 pt-8', wrap: 'glass-card p-4 text-center', ring: 'w-16 h-16 bg-gray-400', icon: <Medal className="w-8 h-8 text-white" />, num: 'text-3xl text-gray-400', tid: 2 },
      { i: 0, order: 'order-2', wrap: 'glass-card p-6 text-center border-gold/30 animate-gold-glow', ring: 'w-20 h-20 bg-gradient-to-br from-gold-start to-gold-end', icon: <Crown className="w-10 h-10 text-black" />, num: 'text-4xl text-gold', tid: 1 },
      { i: 2, order: 'order-3 pt-12', wrap: 'glass-card p-4 text-center', ring: 'w-14 h-14 bg-amber-700', icon: <Medal className="w-7 h-7 text-white" />, num: 'text-2xl text-amber-700', tid: 3 },
    ];
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="grid grid-cols-3 gap-4 mb-8">
        {spots.map((s) => {
          const e = leaderboard[s.i];
          return (
            <div key={s.tid} className={s.order}>
              <div className={s.wrap} data-testid={`leaderboard-rank-${s.tid}`}>
                <div className={`mx-auto mb-3 rounded-full flex items-center justify-center ${s.ring}`}>{s.icon}</div>
                <div className={`font-bold mb-1 ${s.num}`}>{s.tid}</div>
                <h3 className="font-cinzel font-bold text-white truncate">{e?.display_name}</h3>
                <p className="text-gold font-bold">{e?.points} pts</p>
                {e?.rankName ? (
                  <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs ${rankColors[e.rankName]} ${isMaxRank(e.rankName) ? 'text-black' : 'text-white'}`}>{e.rankName}</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </motion.div>
    );
  };

  const renderList = (leaderboard, emptyMsg) => {
    if (leaderboard.length === 0) {
      return (
        <div className="glass-card p-12 text-center" data-testid="leaderboard-empty">
          <Trophy className="w-12 h-12 text-white/20 mx-auto mb-4" />
          <p className="text-white/60 text-lg">{emptyMsg}</p>
        </div>
      );
    }
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass-card overflow-hidden">
        <div className="p-4 border-b border-white/10">
          <h2 className="font-cinzel font-bold text-lg text-white">All Performers</h2>
        </div>
        <div className="divide-y divide-white/5">
          {leaderboard.map((entry, index) => (
            <motion.div
              key={entry.uid || index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + index * 0.03 }}
              className={`flex items-center gap-4 p-4 leaderboard-row ${entry.uid === user?.id ? 'bg-gold/5' : ''}`}
              data-testid={`leaderboard-row-${entry.position}`}
            >
              <div className="w-10 text-center">
                {entry.position <= 3 ? (
                  <div className={`w-8 h-8 mx-auto rounded-full flex items-center justify-center ${entry.position === 1 ? 'bg-gold' : entry.position === 2 ? 'bg-gray-400' : 'bg-amber-700'}`}>
                    {entry.position === 1 ? <Crown className="w-4 h-4 text-black" /> : <span className="text-white font-bold text-sm">{entry.position}</span>}
                  </div>
                ) : (
                  <span className="text-white/60 font-bold">{entry.position}</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-white truncate">{entry.display_name}</h3>
                  {entry.uid === user?.id && <span className="text-xs bg-gold/20 text-gold px-2 py-0.5 rounded-full" data-testid="leaderboard-you-tag">You</span>}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {entry.rankName ? (
                    <span className={`px-2 py-0.5 rounded-full text-xs ${rankColors[entry.rankName]} ${isMaxRank(entry.rankName) ? 'text-black' : 'text-white'}`}>{entry.rankName}</span>
                  ) : null}
                  {activeTab === 'alltime' && entry.songs_performed != null && (
                    <span className="text-white/40 text-xs">{entry.songs_performed} songs</span>
                  )}
                </div>
              </div>
              <div className="text-right">
                <p className="text-gold font-bold text-lg">{entry.points}</p>
                <p className="text-white/40 text-xs">points</p>
              </div>
              <div className="hidden sm:flex items-center gap-1">
                {entry.badges?.slice(0, 3).map((badge, i) => (
                  <div key={i} className="w-6 h-6 bg-white/5 rounded-full flex items-center justify-center"><Star className="w-3 h-3 text-gold" /></div>
                ))}
                {entry.badges?.length > 3 && <span className="text-white/40 text-xs">+{entry.badges.length - 3}</span>}
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    );
  };

  const renderErrorCard = (msg) => (
    <div className="glass-card p-8 text-center border border-red-500/30" data-testid="leaderboard-error">
      <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
      <p className="text-white/70">{msg}</p>
      <button onClick={fetchLeaderboards} className="mt-4 px-4 py-2 rounded-lg bg-gold/20 text-gold hover:bg-gold/30 transition-colors text-sm" data-testid="leaderboard-retry">Retry</button>
    </div>
  );

  const renderSection = (key, list, emptyMsg, subtitle) => (
    <>
      {subtitle && <p className="text-center text-white/50 text-sm mb-4">{subtitle}</p>}
      {errors[key] ? renderErrorCard(errors[key]) : (
        <>
          {renderPodium(list)}
          {userPosition > 0 && activeTab === key && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card p-4 border-gold/30 mb-6" data-testid="user-position">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-gold/10 rounded-lg flex items-center justify-center"><TrendingUp className="w-6 h-6 text-gold" /></div>
                <div>
                  <p className="text-white/60 text-sm">Your {positionLabel} Position</p>
                  <p className="text-white font-bold text-xl">#{userPosition} <span className="text-white/60 font-normal text-base">out of {list.length}</span></p>
                </div>
              </div>
            </motion.div>
          )}
          {renderList(list, emptyMsg)}
        </>
      )}
    </>
  );

  return (
    <Layout>
      <div className="space-y-8" data-testid="leaderboard-page">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-cinzel font-bold text-3xl sm:text-4xl text-white mb-2">Royal <span className="text-gold">Leaderboard</span></h1>
          <p className="text-white/60">The kingdom's finest performers</p>
        </motion.div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full max-w-lg mx-auto grid grid-cols-3 bg-white/5 border border-white/10 rounded-lg p-1">
            <TabsTrigger value="season" className="flex items-center gap-2 data-[state=active]:bg-gold data-[state=active]:text-black rounded-md transition-all" data-testid="season-tab">
              <Calendar className="w-4 h-4" /> Season
            </TabsTrigger>
            <TabsTrigger value="event" className="flex items-center gap-2 data-[state=active]:bg-gold data-[state=active]:text-black rounded-md transition-all" data-testid="event-tab">
              <CalendarDays className="w-4 h-4" /> Event
            </TabsTrigger>
            <TabsTrigger value="alltime" className="flex items-center gap-2 data-[state=active]:bg-gold data-[state=active]:text-black rounded-md transition-all" data-testid="alltime-tab">
              <Trophy className="w-4 h-4" /> All-Time
            </TabsTrigger>
          </TabsList>

          <TabsContent value="season" className="mt-6">
            {renderSection('season', data.season, 'No season points earned yet — check in and sing to climb!', seasonName)}
          </TabsContent>

          <TabsContent value="event" className="mt-6">
            {noActiveEvent && !errors.event ? (
              <div className="glass-card p-12 text-center" data-testid="leaderboard-no-event">
                <CalendarDays className="w-16 h-16 text-white/20 mx-auto mb-4" />
                <h3 className="font-cinzel font-bold text-xl text-white mb-2">No Active Event</h3>
                <p className="text-white/60">Check into an event with the QR code to see its live leaderboard.</p>
              </div>
            ) : (
              renderSection('event', data.event, 'No points scored in this event yet.', eventName ? `Event: ${eventName}` : null)
            )}
          </TabsContent>

          <TabsContent value="alltime" className="mt-6">
            {renderSection('alltime', data.alltime, 'Be the first to claim the throne!', 'Lifetime points across all events')}
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
};

export default LeaderboardPage;
