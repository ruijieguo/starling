import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { connectWs, streamConverse } from './ws';
import { wsConn } from './health';
import * as tok from './token';

class FakeWS {
	static last: FakeWS | null = null;
	onopen: (() => void) | null = null;
	onmessage: ((m: { data: string }) => void) | null = null;
	onerror: (() => void) | null = null;
	onclose: (() => void) | null = null;
	readyState = 1;
	sent: string[] = [];
	constructor(public url: string) {
		FakeWS.last = this;
	}
	send(s: string) {
		this.sent.push(s);
	}
	close() {
		this.readyState = 3;
		this.onclose?.();
	}
}

beforeEach(() => {
	(globalThis as any).WebSocket = FakeWS as any;
	(globalThis as any).WebSocket.OPEN = 1;
	wsConn.set('closed');
});

describe('connectWs', () => {
	it('sets wsConn open on open and parses events', () => {
		const events: unknown[] = [];
		const dispose = connectWs((e) => events.push(e));
		FakeWS.last!.onopen!();
		expect(get(wsConn)).toBe('open');
		FakeWS.last!.onmessage!({ data: JSON.stringify({ type: 'tick', payload: 1 }) });
		expect(events).toEqual([{ type: 'tick', payload: 1 }]);
		dispose();
		expect(get(wsConn)).toBe('closed');
	});
	it('ignores pong frames', () => {
		const events: unknown[] = [];
		connectWs((e) => events.push(e));
		FakeWS.last!.onopen!();
		FakeWS.last!.onmessage!({ data: 'pong' });
		expect(events).toEqual([]);
	});
});

// #37 streaming converse client. The full wire protocol is validated server-side
// in tests/python/test_dashboard_converse_stream.py; these pin the browser
// client's frame dispatch + settle-once guard (reusing the FakeWS double above).
describe('streamConverse', () => {
	beforeEach(() => {
		vi.spyOn(tok, 'getToken').mockReturnValue('secret');
	});

	it('auth-handshakes then sends the request, accumulates deltas, resolves on done', () => {
		const deltas: string[] = [];
		let done: { reply?: string } | null = null;
		streamConverse(
			{ message: 'hi', provider: 'p' },
			{
				onToken: (d) => deltas.push(d),
				onDone: (o) => (done = o),
				onError: () => {
					throw new Error('should not error');
				}
			}
		);
		const ws = FakeWS.last!;
		expect(ws.url).toContain('/ws/converse');
		ws.onopen!();
		expect(ws.sent[0]).toBe('secret'); // in-band token first (mirrors /ws)
		expect(JSON.parse(ws.sent[1])).toEqual({ message: 'hi', provider: 'p' });
		ws.onmessage!({ data: JSON.stringify({ type: 'token', delta: 'Hel' }) });
		ws.onmessage!({ data: JSON.stringify({ type: 'token', delta: 'lo' }) });
		ws.onmessage!({
			data: JSON.stringify({ type: 'done', ok: true, reply: 'Hello', statement_ids: [] })
		});
		expect(deltas).toEqual(['Hel', 'lo']);
		expect(done!.reply).toBe('Hello');
		expect(ws.readyState).toBe(3); // closed by streamConverse on done
	});

	it('dispatches an error frame and settles exactly once (the close it triggers is a no-op)', () => {
		let code = '';
		let count = 0;
		streamConverse(
			{ message: 'hi' },
			{
				onToken: () => {},
				onDone: () => {
					throw new Error('no done expected');
				},
				onError: (c) => {
					code = c;
					count++;
				}
			}
		);
		const ws = FakeWS.last!;
		ws.onopen!();
		ws.onmessage!({ data: JSON.stringify({ type: 'error', error: 'llm_not_configured' }) });
		expect(code).toBe('llm_not_configured');
		expect(count).toBe(1); // ws.close() → onclose → settle no-op
	});

	it('ignores malformed frames but keeps processing valid ones', () => {
		const deltas: string[] = [];
		streamConverse(
			{ message: 'hi' },
			{ onToken: (d) => deltas.push(d), onDone: () => {}, onError: () => {} }
		);
		const ws = FakeWS.last!;
		ws.onopen!();
		ws.onmessage!({ data: 'not json{' });
		ws.onmessage!({ data: JSON.stringify({ type: 'token', delta: 'x' }) });
		expect(deltas).toEqual(['x']);
	});

	it('surfaces a close-without-done as an error, once', () => {
		let count = 0;
		streamConverse(
			{ message: 'hi' },
			{ onToken: () => {}, onDone: () => {}, onError: () => count++ }
		);
		const ws = FakeWS.last!;
		ws.onopen!();
		ws.close(); // closed before any done/error
		expect(count).toBe(1);
	});
});
