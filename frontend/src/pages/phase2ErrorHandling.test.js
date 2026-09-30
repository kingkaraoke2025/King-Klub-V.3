import { errMsg } from '../lib/phase2Api';

// Focused defensive tests for the Phase-2-relevant surfaces now routed through errMsg():
//   - QueuePage add-to-queue  (POST /events/{id}/queue)
//   - QueuePage use-perk       (POST /events/{id}/use-perk)
//   - EventCheckInPage         (POST /e/checkin/{token}, error rendered into JSX/state)
// These mirror exactly how each handler builds its user-facing message, proving a
// structured Pydantic 422 (array of objects) can NEVER reach toast.error()/JSX as an object.

const pydantic422 = {
  response: { data: { detail: [
    { type: 'missing', loc: ['body', 'event_date'], msg: 'Field required', input: {}, url: 'https://errors.pydantic.dev/x' },
  ] } },
};

describe('Phase 2 handler error rendering is crash-safe (errMsg)', () => {
  test('QueuePage add-to-queue: 422 array -> readable string, never an object', () => {
    const out = errMsg(pydantic422, 'Failed to add to queue');
    expect(typeof out).toBe('string');
    expect(out).toBe('Field required: event_date');
  });

  test('QueuePage add-to-queue: normal string detail still shows', () => {
    const e = { response: { data: { detail: 'You have reached your song limit' } } };
    expect(errMsg(e, 'Failed to add to queue')).toBe('You have reached your song limit');
  });

  test('QueuePage use-perk: 422 array -> readable string', () => {
    const out = errMsg(pydantic422, 'Failed to use perk');
    expect(typeof out).toBe('string');
    expect(out).not.toMatch(/\[object Object\]/);
  });

  test('QueuePage use-perk: string detail passes through', () => {
    const e = { response: { data: { detail: 'Perk already used this window' } } };
    expect(errMsg(e, 'Failed to use perk')).toBe('Perk already used this window');
  });

  test('EventCheckInPage: 422 array coerces to a string safe to render in JSX', () => {
    const out = errMsg(pydantic422, 'Check-in failed');
    expect(typeof out).toBe('string');
    // React can render a string child; an object/array would throw "Objects are not valid as a React child".
    expect(Array.isArray(out)).toBe(false);
    expect(out).toBe('Field required: event_date');
  });

  test('EventCheckInPage: string detail (e.g. event not open) passes through', () => {
    const e = { response: { data: { detail: 'Event is not open for check-in' } } };
    expect(errMsg(e, 'Check-in failed')).toBe('Event is not open for check-in');
  });

  test('all three surfaces: fallback used when no response body', () => {
    expect(errMsg(new Error('Network Error'), 'Failed to add to queue')).toBe('Network Error');
    expect(errMsg({}, 'Failed to use perk')).toBe('Failed to use perk');
  });
});
