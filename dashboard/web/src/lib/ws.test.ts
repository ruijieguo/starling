import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { connectWs } from './ws';
import { wsConn } from './health';

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
