import { errMsg } from './phase2Api';

describe('errMsg — safe error stringification (never returns object/array)', () => {
  test('Pydantic 422 detail array -> readable "msg: field"', () => {
    const e = { response: { data: { detail: [
      { type: 'missing', loc: ['body', 'event_date'], msg: 'Field required', input: {}, url: 'https://errors.pydantic.dev/x' },
    ] } } };
    const out = errMsg(e);
    expect(typeof out).toBe('string');
    expect(out).toBe('Field required: event_date');
  });

  test('multiple validation errors are joined into one string', () => {
    const e = { response: { data: { detail: [
      { loc: ['body', 'venue_id'], msg: 'Field required' },
      { loc: ['body', 'event_date'], msg: 'Field required' },
    ] } } };
    const out = errMsg(e);
    expect(typeof out).toBe('string');
    expect(out).toBe('Field required: venue_id; Field required: event_date');
  });

  test('single validation-error object', () => {
    const e = { response: { data: { detail: { msg: 'Bad value', loc: ['body', 'x'] } } } };
    expect(errMsg(e)).toBe('Bad value');
  });

  test('normal string detail is passed through', () => {
    const e = { response: { data: { detail: 'Not authorized for this event' } } };
    expect(errMsg(e)).toBe('Not authorized for this event');
  });

  test('{message:"..."} response body', () => {
    const e = { response: { data: { message: 'Something specific' } } };
    expect(errMsg(e)).toBe('Something specific');
  });

  test('HTTP error without a response falls back to error.message', () => {
    const e = new Error('Network Error');
    expect(errMsg(e)).toBe('Network Error');
  });

  test('completely unexpected error uses provided fallback', () => {
    expect(errMsg({}, 'Save failed')).toBe('Save failed');
    expect(errMsg(null, 'Save failed')).toBe('Save failed');
  });

  test('never returns an object or array', () => {
    const samples = [
      { response: { data: { detail: [{ msg: 'a', loc: ['body', 'f'] }] } } },
      { response: { data: { detail: { msg: 'b' } } } },
      { response: { data: { detail: 'c' } } },
      {},
    ];
    samples.forEach((s) => expect(typeof errMsg(s)).toBe('string'));
  });
});
