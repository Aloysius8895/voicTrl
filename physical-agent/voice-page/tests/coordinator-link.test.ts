// 语音页 -> 总控：把语音助手说完的每一轮文字发给总控（再由总控推到手表）。
// Seam: CoordinatorLink（浏览器的 WebSocket 换成假的）。运行：在 voice-page 目录下 `bun test`。
import { expect, test } from "bun:test";

import {
	CoordinatorLink,
	deviceTokenFromHash,
} from "../web/src/lib/coordinator-link";

class FakeSocket {
	static last: FakeSocket;
	sent: Array<{ type: string; payload: Record<string, unknown> }> = [];
	onopen: (() => void) | null = null;
	onmessage: ((event: { data: string }) => void) | null = null;
	onclose: (() => void) | null = null;
	closed = false;
	constructor(public url: string) {
		FakeSocket.last = this;
	}
	send(raw: string) {
		this.sent.push(JSON.parse(raw));
	}
	close() {
		this.closed = true;
	}
	// what the coordinator would do
	open() {
		this.onopen?.();
	}
	ackHello() {
		this.onmessage?.({
			data: JSON.stringify({
				type: "hello_ack",
				payload: { device_id: "phone-1", kind: "phone" },
			}),
		});
	}
}

const assistant = (turn_id: number, text: string, turn_status: number) => ({
	turn_id,
	text,
	status: 1, // the toolkit hard-codes END here in TEXT mode; metadata.turn_status is the truth
	metadata: { object: "assistant.transcription", turn_status },
});
const user = (turn_id: number, text: string) => ({
	turn_id,
	text,
	status: 1,
	metadata: { object: "user.transcription", final: true },
});

function connected() {
	const link = new CoordinatorLink("ws://coordinator/ws/device", "phone-token", FakeSocket);
	link.connect();
	const socket = FakeSocket.last;
	socket.open();
	socket.ackHello();
	return { link, socket };
}

test("the first thing sent on the socket is a hello with the device token", () => {
	const link = new CoordinatorLink("ws://coordinator/ws/device", "phone-token", FakeSocket);
	link.connect();
	FakeSocket.last.open();

	expect(FakeSocket.last.url).toBe("ws://coordinator/ws/device");
	expect(FakeSocket.last.sent).toEqual([{ type: "hello", payload: { token: "phone-token" } }]);
});

test("a finished assistant turn is forwarded as an agent_transcript", () => {
	const { link, socket } = connected();

	link.forward([user(1, "wake laptop A"), assistant(1, "Laptop A is awake.", 1)]);

	expect(socket.sent.slice(1)).toEqual([
		{ type: "agent_transcript", payload: { text: "Laptop A is awake.", turn_id: 1, final: true } },
	]);
});

test("a turn still being spoken waits, and each turn is sent once although the page gets the whole list every time", () => {
	const { link, socket } = connected();

	link.forward([assistant(1, "Laptop A is", 0)]);
	link.forward([assistant(1, "Laptop A is awake.", 1)]);
	link.forward([assistant(1, "Laptop A is awake.", 1), assistant(2, "Copying", 0)]);
	link.forward([assistant(1, "Laptop A is awake.", 1), assistant(2, "Copying file one.", 2)]);

	expect(socket.sent.slice(1).map((frame) => frame.payload.text)).toEqual([
		"Laptop A is awake.",
		"Copying file one.", // turn_status 2 = interrupted: it is over, so it is forwarded too
	]);
});

test("turns that finish before the coordinator has answered the hello are sent once it does", () => {
	const link = new CoordinatorLink("ws://coordinator/ws/device", "phone-token", FakeSocket);
	link.connect();
	const socket = FakeSocket.last;
	socket.open();

	link.forward([assistant(1, "Laptop A is awake.", 1)]);
	const beforeAck = socket.sent.length;
	socket.ackHello();

	expect(beforeAck).toBe(1); // only the hello
	expect(socket.sent.slice(1).map((frame) => frame.payload.text)).toEqual(["Laptop A is awake."]);
});

test("the device token comes from the link's #token= part", () => {
	expect(deviceTokenFromHash("#token=abc-_123")).toBe("abc-_123");
	expect(deviceTokenFromHash("#other=1&token=abc")).toBe("abc");
	expect(deviceTokenFromHash("")).toBeNull();
	expect(deviceTokenFromHash("#token=")).toBeNull();
});
