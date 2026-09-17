import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { QrCode, RefreshCw, Users, Clock, Download, Copy, Check, CalendarDays } from 'lucide-react';
import { Layout } from '@/components/Layout';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { p2, qrImage, FRONTEND_URL } from '@/lib/phase2Api';

// Phase 2 event-scoped QR. This page was migrated from the retired legacy
// nightly venue QR (/api/venue/qr-data) to the Phase 2 event QR endpoint
// (GET /api/admin/events/{id}/qr) which returns a signed, expiring, tamper-proof
// token whose check-in path is /e/checkin/{token}. No QR backend changes.
const QRCheckInPage = () => {
  const [events, setEvents] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [qr, setQr] = useState(null);
  const [singers, setSingers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [qrLoading, setQrLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const selectedEvent = events.find((e) => e.id === selectedId) || null;
  const checkinUrl = qr ? `${FRONTEND_URL}${qr.checkin_path}` : '';

  useEffect(() => {
    (async () => {
      try {
        const evs = await p2.events();
        setEvents(evs);
        const active = evs.find((e) => e.status === 'active') || evs[0];
        if (active) setSelectedId(active.id);
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to load events');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const loadQR = async (eventId) => {
    if (!eventId) return;
    setQrLoading(true);
    try {
      const [qrRes, listRes] = await Promise.all([
        p2.eventQR(eventId),
        p2.singerList(eventId).catch(() => ({ singers: [] })),
      ]);
      setQr(qrRes);
      setSingers(listRes.singers || []);
    } catch (e) {
      setQr(null);
      toast.error(e.response?.data?.detail || 'Failed to generate event QR');
    } finally {
      setQrLoading(false);
    }
  };

  useEffect(() => { if (selectedId) loadQR(selectedId); /* eslint-disable-next-line */ }, [selectedId]);

  const handleDownloadQR = () => {
    if (!qr) return;
    const link = document.createElement('a');
    link.href = qrImage(checkinUrl);
    link.download = `king-klub-event-${selectedEvent?.name || 'qr'}.png`;
    link.click();
  };

  const copyUrl = () => {
    navigator.clipboard.writeText(checkinUrl);
    setCopied(true);
    toast.success('Check-in URL copied');
    setTimeout(() => setCopied(false), 1500);
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-gold animate-pulse font-cinzel text-2xl">Loading Events...</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-8" data-testid="qr-checkin-page">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <QrCode className="w-6 h-6 text-gold" />
              <h1 className="font-cinzel font-bold text-3xl sm:text-4xl text-white">
                Event <span className="text-gold">QR Check-In</span>
              </h1>
            </div>
            <p className="text-white/60">Select an event and display its QR for singer check-ins</p>
          </div>
          <Button onClick={() => loadQR(selectedId)} data-testid="refresh-qr-btn" disabled={!selectedId || qrLoading}
            className="bg-white/5 border border-white/20 hover:bg-white/10 text-white">
            <RefreshCw className={`w-4 h-4 mr-2 ${qrLoading ? 'animate-spin' : ''}`} />
            Regenerate
          </Button>
        </motion.div>

        {/* Event selector */}
        <div className="glass-card p-5" data-testid="event-selector-card">
          <label className="text-sm text-white/60 flex items-center gap-2 mb-2"><CalendarDays className="w-4 h-4 text-gold" /> Select Event</label>
          {events.length === 0 ? (
            <p className="text-white/50">No events available. Create one in Phase 2 Admin → Events.</p>
          ) : (
            <select data-testid="qr-event-select" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}
              className="w-full md:w-2/3 bg-black/40 border border-white/15 rounded-lg px-3 py-2 text-white focus:border-gold outline-none">
              {events.map((ev) => (
                <option key={ev.id} value={ev.id}>{ev.name} — {ev.event_date} ({ev.status})</option>
              ))}
            </select>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* QR Code Display */}
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 }}
            className="glass-card p-8 text-center">
            <h2 className="font-cinzel font-bold text-xl text-white mb-2">Scan to Check In</h2>
            {selectedEvent && <p className="text-gold mb-6" data-testid="qr-event-name">{selectedEvent.name}</p>}

            {qrLoading ? (
              <div className="text-gold animate-pulse py-24">Generating QR…</div>
            ) : qr ? (
              <>
                <div className="bg-white rounded-2xl p-4 inline-block mb-6">
                  <img src={qrImage(checkinUrl)} alt="Event Check-in QR Code" className="w-64 h-64 mx-auto" data-testid="qr-code-image" />
                </div>
                <div className="space-y-4">
                  {qr.expires_at && (
                    <div className="flex items-center justify-center gap-2 text-gold text-sm">
                      <Clock className="w-4 h-4" /> Expires: {new Date(qr.expires_at).toLocaleString()}
                    </div>
                  )}
                  <div className="flex items-center gap-2 bg-black/40 border border-white/15 rounded-lg px-3 py-2 max-w-md mx-auto">
                    <span className="text-white/60 text-sm truncate flex-1 text-left" data-testid="qr-checkin-url">{checkinUrl}</span>
                    <button data-testid="copy-qr-url-btn" onClick={copyUrl} className="text-gold hover:brightness-110">
                      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                  <Button onClick={handleDownloadQR} data-testid="download-qr-btn" className="btn-gold">
                    <Download className="w-4 h-4 mr-2" /> Download QR Code
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-white/50 py-24">Select an event to generate its QR.</div>
            )}
          </motion.div>

          {/* Event singers (event-scoped) */}
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
            className="glass-card overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h2 className="font-cinzel font-bold text-lg text-white">Checked-in Singers</h2>
              <div className="flex items-center gap-2 bg-gold/10 px-3 py-1 rounded-full">
                <Users className="w-4 h-4 text-gold" />
                <span className="text-gold font-bold" data-testid="singer-count">{singers.length}</span>
              </div>
            </div>
            <div className="max-h-[400px] overflow-y-auto" data-testid="event-singers-list">
              {singers.length === 0 ? (
                <div className="p-8 text-center">
                  <Users className="w-10 h-10 text-white/20 mx-auto mb-3" />
                  <p className="text-white/60">No singers checked in yet</p>
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {singers.map((s, index) => (
                    <motion.div key={s.user_id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }} className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-gold font-cinzel font-bold w-6">{s.list_position}</span>
                        <div>
                          <p className="text-white font-medium">{s.display_name}</p>
                          <p className="text-white/40 text-sm">{s.status}</p>
                        </div>
                      </div>
                      <span className="text-gold text-sm">{s.event_points} pts</span>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass-card p-6">
          <h3 className="font-cinzel font-bold text-lg text-white mb-4">How It Works</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[['1', 'Select the event and display its QR'], ['2', 'Singers scan with their phone'], ['3', 'They check into that event & earn points']].map(([n, t]) => (
              <div key={n} className="text-center">
                <div className="w-12 h-12 bg-gold/10 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-gold font-bold text-xl">{n}</span>
                </div>
                <p className="text-white/80">{t}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </Layout>
  );
};

export default QRCheckInPage;
