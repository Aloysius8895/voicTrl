// Sample mode: one scripted run of the demo task, as a pure function of time.
// Every number and line here is example data; the UI labels it "Sample".

export type CallState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "ended";
export type StepState = "waiting" | "executing" | "done" | "needs-you" | "cancelled" | "failed";
export type TaskState = "not-started" | "running" | "needs-you" | "done" | "cancelled";
export type DeviceState = "asleep" | "waking" | "online" | "offline";
export type Decision = "confirmed" | "cancelled";

export interface ToolCall {
	name: string;
	args: Record<string, string>;
}

export interface Step {
	id: string;
	title: string;
	summary: string;
	/** Why the assistant took this step, in its own words. */
	reason: string;
	tool: ToolCall;
	/** How the step is carried out, shown under "Execute". */
	how: string;
	/** What happened, once the step is done. */
	result: string;
	state: StepState;
	/** 0..1 while executing. */
	progress: number;
}

export interface Device {
	id: string;
	name: string;
	kind: "laptop" | "watch" | "phone";
	state: DeviceState;
	detail: string;
}

export interface Evidence {
	id: string;
	label: string;
	value: string | null;
	detail: string;
	/** A code (hash, run code) rather than a measurement. */
	code?: boolean;
}

export interface Subtitle {
	speaker: "you" | "assistant";
	text: string;
}

export interface Run {
	call: { state: CallState; subtitles: Subtitle[]; seconds: number };
	task: { title: string; state: TaskState };
	steps: Step[];
	devices: Device[];
	evidence: Evidence[];
}

export interface Choices {
	decision?: Decision;
	/** Elapsed ms at which the user hung up, if they did. */
	hungUpAt?: number;
}

interface StepSpec extends Omit<Step, "state" | "progress"> {
	durationMs: number;
}

const STEPS: StepSpec[] = [
	{
		id: "wake-a",
		title: "Wake Laptop A",
		summary: "Brings A out of sleep.",
		reason: "You want to start on Laptop A, and it is asleep.",
		tool: { name: "wakeDevice", args: { device: "laptop-a" } },
		how: "USB waker · remote wake",
		result: "Awake in 4.1 s",
		durationMs: 4100,
	},
	{
		id: "wake-b",
		title: "Wake Laptop B",
		summary: "B will build the page.",
		reason: "Laptop B has Claude Code, so the page is built there.",
		tool: { name: "wakeDevice", args: { device: "laptop-b" } },
		how: "Wi-Fi waker · magic packet",
		result: "Awake in 7.8 s",
		durationMs: 7800,
	},
	{
		id: "send-file",
		title: "Send file1.md to B",
		summary: "Moves the prompt file across.",
		reason: "The page is described in file1.md, which lives on Laptop A.",
		tool: { name: "copyFile", args: { from: "laptop-a", to: "laptop-b", file: "file1.md" } },
		how: "Transfer · SHA-256 check",
		result: "Same SHA-256 on A and B",
		durationMs: 2400,
	},
	{
		id: "build",
		title: "Build the page on B",
		summary: "Claude Code writes it.",
		reason: "file1.md asks for a Hello World page with today's run code.",
		tool: { name: "buildOnDevice", args: { device: "laptop-b", prompt: "file1.md" } },
		how: "Claude Code · index.html",
		result: "3 of 3 page checks passed",
		durationMs: 12000,
	},
	{
		id: "open",
		title: "Open the result on A",
		summary: "Shows it where you are.",
		reason: "You asked to see it on Laptop A.",
		tool: { name: "openResult", args: { device: "laptop-a" } },
		how: "VS Code + browser preview",
		result: "Confirmed by you",
		durationMs: 3000,
	},
];

const TASK_TITLE = "Build a Hello World page on B, show it on A";

const CONNECT_MS = 1200;
const GREET_MS = 2600;
const REQUEST_MS = 3400;
const THINK_MS = 1200;
const ACK_MS = 2300;

const greetAt = CONNECT_MS;
const userSpeaksAt = greetAt + GREET_MS;
const thinkAt = userSpeaksAt + REQUEST_MS;
const taskStartsAt = thinkAt + THINK_MS;
const stepStarts = STEPS.reduce<number[]>((starts, _step, i) => {
	starts.push(i === 0 ? taskStartsAt : starts[i - 1] + STEPS[i - 1].durationMs);
	return starts;
}, []);
const allStepsDoneAt = stepStarts[STEPS.length - 1] + STEPS[STEPS.length - 1].durationMs;
const ASK_MS = 3200;

export const SAMPLE_TIMING = { greetAt, userSpeaksAt, taskStartsAt, allStepsDoneAt } as const;

/** What the call sounds like at each moment: [from ms, state, line said at that moment]. */
const CALL_SCRIPT: Array<[number, CallState, Subtitle | null]> = [
	[0, "connecting", null],
	[greetAt, "speaking", { speaker: "assistant", text: "Hi, I'm listening. What should your devices do?" }],
	[userSpeaksAt, "listening", { speaker: "you", text: "Wake A and B, send file one to B, build the page there and show me on A." }],
	[thinkAt, "thinking", null],
	[taskStartsAt, "speaking", { speaker: "assistant", text: "On it. Five steps, starting with Laptop A." }],
	[taskStartsAt + ACK_MS, "listening", null],
	[stepStarts[3], "speaking", { speaker: "assistant", text: "B is awake and has the file. Claude is building the page." }],
	[stepStarts[3] + ACK_MS, "listening", null],
	[allStepsDoneAt, "speaking", { speaker: "assistant", text: "It's open on Laptop A. Say confirm if it looks right." }],
	[allStepsDoneAt + ASK_MS, "listening", null],
];

const DEVICES: Array<Omit<Device, "state" | "detail">> = [
	{ id: "laptop-a", name: "Laptop A", kind: "laptop" },
	{ id: "laptop-b", name: "Laptop B", kind: "laptop" },
	{ id: "watch", name: "Watch", kind: "watch" },
	{ id: "phone", name: "This phone", kind: "phone" },
];

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

function stepStateAt(i: number, t: number, decision?: Decision): { state: StepState; progress: number } {
	const start = stepStarts[i];
	const end = start + STEPS[i].durationMs;
	if (t < start) return { state: "waiting", progress: 0 };
	if (t < end) return { state: "executing", progress: clamp01((t - start) / STEPS[i].durationMs) };
	const isLast = i === STEPS.length - 1;
	if (!isLast) return { state: "done", progress: 1 };
	if (decision === "confirmed") return { state: "done", progress: 1 };
	if (decision === "cancelled") return { state: "cancelled", progress: 1 };
	return { state: "needs-you", progress: 1 };
}

function laptopAt(wakeStep: number, t: number | null): Pick<Device, "state" | "detail"> {
	if (t === null || t < stepStarts[wakeStep]) return { state: "asleep", detail: "Sleeping · waker armed" };
	if (t < stepStarts[wakeStep] + STEPS[wakeStep].durationMs) return { state: "waking", detail: STEPS[wakeStep].how };
	return { state: "online", detail: `${STEPS[wakeStep].result} · connected` };
}

function callAt(t: number | null, choices: Choices): Run["call"] {
	if (t === null) return { state: "idle", subtitles: [], seconds: 0 };
	if (choices.hungUpAt !== undefined && t >= choices.hungUpAt) {
		return { state: "ended", subtitles: [], seconds: Math.floor(choices.hungUpAt / 1000) };
	}
	let state: CallState = "connecting";
	const said: Subtitle[] = [];
	for (const [from, s, line] of CALL_SCRIPT) {
		if (t < from) break;
		state = s;
		if (line) said.push(line);
	}
	if (choices.decision && t >= allStepsDoneAt) {
		said.push({ speaker: "you", text: choices.decision === "confirmed" ? "Confirm." : "Cancel." });
		said.push({
			speaker: "assistant",
			text: choices.decision === "confirmed" ? "Confirmed. All done." : "Cancelled. Nothing else will run.",
		});
		state = "listening";
	}
	return { state, subtitles: said.slice(-2), seconds: Math.floor(t / 1000) };
}

/**
 * The sample run `elapsedMs` after the call started (null: no call yet).
 * The task keeps running on the devices if the user hangs up.
 */
export function sampleRunAt(elapsedMs: number | null, choices: Choices = {}): Run {
	const t = elapsedMs;
	const steps: Step[] = STEPS.map((spec, i) => {
		const { durationMs: _ignored, ...step } = spec;
		const { state, progress } = t === null ? { state: "waiting" as const, progress: 0 } : stepStateAt(i, t, choices.decision);
		return { ...step, state, progress };
	});

	let taskState: TaskState = "not-started";
	if (t !== null && t >= taskStartsAt) taskState = "running";
	const last = steps[steps.length - 1].state;
	if (last === "needs-you") taskState = "needs-you";
	if (last === "done") taskState = "done";
	if (last === "cancelled") taskState = "cancelled";

	const done = (id: string) => steps.find((s) => s.id === id)?.state === "done";
	const devices: Device[] = DEVICES.map((d) => {
		if (d.id === "laptop-a") return { ...d, ...laptopAt(0, t) };
		if (d.id === "laptop-b") return { ...d, ...laptopAt(1, t) };
		if (d.id === "watch") return { ...d, state: "online", detail: "Listening for you" };
		return { ...d, state: "online", detail: t === null ? "Ready to call" : "On the call" };
	});

	const evidence: Evidence[] = [
		{ id: "wake-a", label: "Laptop A woke in", value: done("wake-a") ? "4.1 s" : null, detail: "From sleep, USB waker" },
		{ id: "wake-b", label: "Laptop B woke in", value: done("wake-b") ? "7.8 s" : null, detail: "From sleep, Wi-Fi waker" },
		{ id: "file-hash", label: "file1.md SHA-256", value: done("send-file") ? "9f2c…41ab" : null, detail: "Same on A and B", code: true },
		{ id: "nonce", label: "Run code in page", value: done("build") ? "DEMO-7F3A" : null, detail: "Found in index.html", code: true },
	];

	return {
		call: callAt(t, choices),
		task: { title: TASK_TITLE, state: taskState },
		steps,
		devices,
		evidence,
	};
}

/** Fixed moments of the sample run, for screenshots and links like ?scene=building. */
export const SCENES = ["idle", "listening", "waking", "building", "confirm", "done"] as const;
export type SceneName = (typeof SCENES)[number];

const SCENE_AT: Record<SceneName, { t: number | null; choices?: Choices }> = {
	idle: { t: null },
	listening: { t: userSpeaksAt + 1500 },
	waking: { t: stepStarts[1] + STEPS[1].durationMs * 0.55 },
	building: { t: stepStarts[3] + STEPS[3].durationMs * 0.62 },
	confirm: { t: allStepsDoneAt + 1500 },
	done: { t: allStepsDoneAt + 6000, choices: { decision: "confirmed" } },
};

export function sceneTime(name: SceneName): { t: number | null; choices: Choices } {
	return { t: SCENE_AT[name].t, choices: SCENE_AT[name].choices ?? {} };
}

export function scene(name: SceneName): Run {
	const { t, choices } = sceneTime(name);
	return sampleRunAt(t, choices);
}
