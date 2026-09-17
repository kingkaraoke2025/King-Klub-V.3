import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const FRONTEND_URL = window.location.origin;

export const STAFF_ROLES = ['global_admin', 'location_manager', 'venue_kj'];
export const isStaff = (u) => !!u && (u.is_admin || STAFF_ROLES.includes(u.role));
export const isGlobalAdmin = (u) => !!u && (u.role === 'global_admin' || (u.is_admin && !u.role));
export const roleLabel = (r) => ({
  global_admin: 'Global Admin', location_manager: 'Location Manager',
  venue_kj: 'Venue KJ', singer: 'Singer',
}[r] || r || 'Singer');

export const p2 = {
  locations: () => axios.get(`${API}/admin/locations`).then((r) => r.data),
  createLocation: (d) => axios.post(`${API}/admin/locations`, d).then((r) => r.data),
  updateLocation: (id, d) => axios.put(`${API}/admin/locations/${id}`, d).then((r) => r.data),
  venues: (locationId) => axios.get(`${API}/admin/venues`, { params: locationId ? { location_id: locationId } : {} }).then((r) => r.data),
  createVenue: (d) => axios.post(`${API}/admin/venues`, d).then((r) => r.data),
  updateVenue: (id, d) => axios.put(`${API}/admin/venues/${id}`, d).then((r) => r.data),
  events: () => axios.get(`${API}/admin/events`).then((r) => r.data),
  event: (id) => axios.get(`${API}/admin/events/${id}`).then((r) => r.data),
  createEvent: (d) => axios.post(`${API}/admin/events`, d).then((r) => r.data),
  updateEvent: (id, d) => axios.put(`${API}/admin/events/${id}`, d).then((r) => r.data),
  eventQR: (id) => axios.get(`${API}/admin/events/${id}/qr`).then((r) => r.data),
  singerList: (id) => axios.get(`${API}/events/${id}/singer-list`).then((r) => r.data),
  eventQueue: (id) => axios.get(`${API}/events/${id}/queue`).then((r) => r.data),
  eventLeaderboard: (id) => axios.get(`${API}/events/${id}/leaderboard`).then((r) => r.data),
  seasonLeaderboard: () => axios.get(`${API}/seasons/current/leaderboard`).then((r) => r.data),
  seasonCurrent: () => axios.get(`${API}/seasons/current`).then((r) => r.data),
  completeSong: (eid, iid) => axios.post(`${API}/events/${eid}/queue/${iid}/complete`).then((r) => r.data),
  setCurrent: (eid, iid) => axios.post(`${API}/events/${eid}/queue/${iid}/set-current`).then((r) => r.data),
  moveUp: (eid, iid) => axios.post(`${API}/events/${eid}/queue/${iid}/move-up`).then((r) => r.data),
  moveDown: (eid, iid) => axios.post(`${API}/events/${eid}/queue/${iid}/move-down`).then((r) => r.data),
  awardPoints: (eid, body) => axios.post(`${API}/events/${eid}/award-points`, body).then((r) => r.data),
  checkin: (token) => axios.post(`${API}/e/checkin/${token}`).then((r) => r.data),
};

export const qrImage = (url) =>
  `https://api.qrserver.com/v1/create-qr-code/?size=320x320&data=${encodeURIComponent(url)}&bgcolor=1A0B2E&color=FFD700`;

export const STATUS_COLORS = {
  active: 'bg-green-500/20 text-green-300 border-green-500/40',
  scheduled: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  draft: 'bg-gray-500/20 text-gray-300 border-gray-500/40',
  ended: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  cancelled: 'bg-red-500/20 text-red-300 border-red-500/40',
  archived: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
};
