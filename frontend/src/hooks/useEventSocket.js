import { useEffect, useRef } from 'react';

/**
 * Phase 2 per-event realtime subscription.
 *
 * Connects to the authenticated, event-scoped WS room:  /api/ws/events/{eventId}?token=...
 * The backend validates the JWT + role + venue/location/event scope on connect
 * (authz.require_event_view), so a client can only ever receive events it is
 * authorized to see. This hook never weakens that — it only consumes.
 *
 * Design (matches the required "initial state + realtime deltas" contract):
 *   - onReady()  fires on every (re)connect  -> the page refetches AUTHORITATIVE state.
 *   - onMessage(msg) fires for each realtime delta -> the page refetches the affected slice.
 * Because the page always refetches authoritative state, duplicate / out-of-order /
 * reconnect / stale messages converge safely (idempotent) and never append dupes.
 *
 * Isolation on switch: when `eventId` changes the effect tears down the old socket
 * (unsubscribe + clear reconnect timer) BEFORE opening the new one, and every inbound
 * message is dropped unless its embedded event_id matches the currently subscribed event,
 * so a slow message from event A can never mutate event B's UI.
 */
const useEventSocket = (eventId, token, handlers = {}) => {
  const handlersRef = useRef(handlers);
  // Keep the latest handlers without reconnecting the socket (avoids stale closures).
  useEffect(() => { handlersRef.current = handlers; });

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const pingRef = useRef(null);
  const shouldRef = useRef(true);
  const attemptsRef = useRef(0);

  useEffect(() => {
    if (!eventId || !token) return undefined;
    shouldRef.current = true;
    attemptsRef.current = 0;
    const currentEvent = eventId;

    const clearTimers = () => {
      if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
      if (reconnectRef.current) { clearTimeout(reconnectRef.current); reconnectRef.current = null; }
    };

    const teardown = () => {
      clearTimers();
      if (wsRef.current) {
        try { wsRef.current.onclose = null; wsRef.current.onmessage = null; wsRef.current.onerror = null; wsRef.current.close(); } catch (_) {}
        wsRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (!shouldRef.current || reconnectRef.current) return;
      attemptsRef.current += 1;
      const delay = Math.min(1000 * 2 ** Math.min(attemptsRef.current, 4), 15000); // 2s → 15s backoff
      reconnectRef.current = setTimeout(() => { reconnectRef.current = null; connect(); }, delay);
    };

    const connect = () => {
      if (!shouldRef.current) return;
      // Ensure only ONE live socket per subscription (no duplicate connections/handlers).
      if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
      if (wsRef.current) { try { wsRef.current.onclose = null; wsRef.current.close(); } catch (_) {} wsRef.current = null; }

      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${proto}//${window.location.host}/api/ws/events/${currentEvent}?token=${encodeURIComponent(token)}`;
      let ws;
      try { ws = new WebSocket(url); } catch (_) { scheduleReconnect(); return; }
      wsRef.current = ws;

      ws.onopen = () => {
        attemptsRef.current = 0;
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) { try { ws.send('ping'); } catch (_) {} }
        }, 30000);
        // Re-fetch authoritative state on connect AND on every reconnect (reconcile).
        try { handlersRef.current.onReady && handlersRef.current.onReady(); } catch (_) {}
      };

      ws.onmessage = (e) => {
        if (!e.data || e.data === 'pong') return;
        let msg;
        try { msg = JSON.parse(e.data); } catch (_) { return; }
        // Stale / cross-event guard: ignore anything not for the subscribed event.
        if (msg.event_id && msg.event_id !== currentEvent) return;
        try { handlersRef.current.onMessage && handlersRef.current.onMessage(msg); } catch (_) {}
      };

      ws.onclose = () => {
        if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
        if (wsRef.current === ws) wsRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = () => { try { ws.close(); } catch (_) {} };
    };

    connect();

    return () => {
      shouldRef.current = false;
      teardown();
    };
  }, [eventId, token]);
};

export default useEventSocket;
