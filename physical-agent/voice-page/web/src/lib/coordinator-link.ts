// Added for physical-agent (not part of Agora's sample).
//
// The voice page is the only place that receives what the voice assistant says
// as text. This link passes each finished assistant turn on to the coordinator,
// which shows it on the watch. It speaks the coordinator's device protocol:
// one hello frame carrying the phone's device token, then agent_transcript frames.

const TOKEN_KEY = "pagent.deviceToken";
const RECONNECT_MS = 2000;
const TURN_IN_PROGRESS = 0; // the toolkit's TurnStatus.IN_PROGRESS

type TranscriptItem = {
	turn_id?: number;
	text?: string;
	status?: number;
	metadata?: { object?: string; turn_status?: number } | null;
};

type SocketLike = {
	send(data: string): void;
	close(): void;
	onopen: ((event: unknown) => void) | null;
	onmessage: ((event: { data: unknown }) => void) | null;
	onclose: ((event: unknown) => void) | null;
};
type SocketConstructor = new (url: string) => SocketLike;

/** The device token in a link's `#token=...` part. The part after `#` never leaves the browser. */
export function deviceTokenFromHash(hash: string): string | null {
	return new URLSearchParams(hash.replace(/^#/, "")).get("token") || null;
}

/**
 * The phone's device token: taken from the link the page was opened with, then
 * kept for this tab only, and removed from the address bar.
 */
export function deviceToken(): string | null {
	if (typeof window === "undefined") return null;
	const fromLink = deviceTokenFromHash(window.location.hash);
	if (fromLink) {
		window.sessionStorage.setItem(TOKEN_KEY, fromLink);
		window.history.replaceState(null, "", window.location.pathname + window.location.search);
		return fromLink;
	}
	return window.sessionStorage.getItem(TOKEN_KEY);
}

/** Where the coordinator's device socket is: configured, or on the page's own host. */
export function coordinatorSocketUrl(): string {
	const configured = process.env.NEXT_PUBLIC_COORDINATOR_WS_URL;
	if (configured) return configured;
	const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
	return `${scheme}//${window.location.host}/ws/device`;
}

export class CoordinatorLink {
	private socket: SocketLike | null = null;
	private ready = false; // the coordinator has answered our hello
	private closed = false;
	private waiting: string[] = [];
	private sentTurns = new Set<number>();

	constructor(
		private url: string,
		private token: string,
		private Socket: SocketConstructor = WebSocket as unknown as SocketConstructor,
	) {}

	connect(): void {
		if (this.closed) return;
		const socket = new this.Socket(this.url);
		this.socket = socket;
		this.ready = false;
		socket.onopen = () => {
			socket.send(JSON.stringify({ type: "hello", payload: { token: this.token } }));
		};
		socket.onmessage = (event) => {
			let type: unknown;
			try {
				type = JSON.parse(String(event.data)).type;
			} catch {
				return;
			}
			if (type === "hello_ack") {
				this.ready = true;
				for (const frame of this.waiting.splice(0)) socket.send(frame);
			}
		};
		socket.onclose = () => {
			this.ready = false;
			if (!this.closed) setTimeout(() => this.connect(), RECONNECT_MS);
		};
	}

	/** Give it the transcript list as the toolkit delivers it (the whole conversation, every time). */
	forward(items: readonly TranscriptItem[]): void {
		for (const item of items) {
			if (item.metadata?.object !== "assistant.transcription") continue;
			if ((item.metadata.turn_status ?? item.status) === TURN_IN_PROGRESS) continue;
			const text = item.text?.trim();
			if (!text || item.turn_id === undefined || this.sentTurns.has(item.turn_id)) continue;
			this.sentTurns.add(item.turn_id);
			this.send(
				JSON.stringify({
					type: "agent_transcript",
					payload: { text, turn_id: item.turn_id, final: true },
				}),
			);
		}
	}

	close(): void {
		this.closed = true;
		this.socket?.close();
	}

	private send(frame: string): void {
		if (this.ready && this.socket) this.socket.send(frame);
		else this.waiting.push(frame);
	}
}
