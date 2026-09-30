import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Crown, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { p2, errMsg } from '@/lib/phase2Api';

const EventCheckInPage = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [state, setState] = useState({ status: 'working', data: null, error: null });

  useEffect(() => {
    if (loading) return;
    if (!user) { navigate(`/login?redirect=${encodeURIComponent(`/e/checkin/${token}`)}`, { replace: true }); return; }
    (async () => {
      try {
        const data = await p2.checkin(token);
        setState({ status: 'ok', data, error: null });
      } catch (e) {
        setState({ status: 'error', data: null, error: errMsg(e, 'Check-in failed') });
      }
    })();
  }, [user, loading, token, navigate]);

  return (
    <div className="min-h-screen bg-royal-bg flex items-center justify-center p-4">
      <div className="glass-card p-8 border border-gold/30 max-w-md w-full text-center" data-testid="event-checkin-result">
        <Crown className="w-12 h-12 text-gold mx-auto mb-4" />
        {state.status === 'working' && (
          <div className="text-white/70 flex flex-col items-center gap-3"><Loader2 className="w-8 h-8 animate-spin text-gold" /> Checking you in…</div>
        )}
        {state.status === 'ok' && (
          <div data-testid="checkin-success">
            <CheckCircle2 className="w-12 h-12 text-green-400 mx-auto mb-3" />
            <h1 className="font-cinzel text-2xl text-white mb-2">{state.data.already_checked_in ? "You're already in!" : 'Checked In!'}</h1>
            <p className="text-white/60">{state.data.message}</p>
            {state.data.list_position && <p className="text-gold mt-2">You are #{state.data.list_position} on the singer list</p>}
            <button onClick={() => navigate('/dashboard')} className="mt-6 bg-gold text-black font-semibold px-5 py-2 rounded-full">Go to Dashboard</button>
          </div>
        )}
        {state.status === 'error' && (
          <div data-testid="checkin-error">
            <XCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
            <h1 className="font-cinzel text-2xl text-white mb-2">Check-in Failed</h1>
            <p className="text-white/60">{state.error}</p>
            <button onClick={() => navigate('/dashboard')} className="mt-6 border border-gold/40 text-gold px-5 py-2 rounded-full">Back to Dashboard</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default EventCheckInPage;
