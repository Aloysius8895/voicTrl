// 样品模式：一次示例运行在任意时刻的样子。界面只负责把它画出来。
// Seam: sampleRunAt(elapsedMs, choices) 和 scene(name)。
import { describe, expect, test } from "vitest";

import { SAMPLE_TIMING, sampleRunAt, scene, SCENES } from "./sampleRun";

const stateOf = (run: ReturnType<typeof sampleRunAt>, stepId: string) =>
	run.steps.find((s) => s.id === stepId)?.state;
const deviceState = (run: ReturnType<typeof sampleRunAt>, id: string) =>
	run.devices.find((d) => d.id === id)?.state;

describe("before the call", () => {
	test("nothing is running, both laptops are asleep and there is no evidence yet", () => {
		const run = sampleRunAt(null);

		expect(run.call.state).toBe("idle");
		expect(run.task.state).toBe("not-started");
		expect(run.steps.map((s) => s.state)).toEqual(["waiting", "waiting", "waiting", "waiting", "waiting"]);
		expect(deviceState(run, "laptop-a")).toBe("asleep");
		expect(deviceState(run, "laptop-b")).toBe("asleep");
		expect(run.evidence.every((e) => e.value === null)).toBe(true);
	});
});

describe("during the run", () => {
	test("the call connects, the assistant greets, then listens to the request", () => {
		expect(sampleRunAt(200).call.state).toBe("connecting");
		expect(sampleRunAt(SAMPLE_TIMING.greetAt + 100).call.state).toBe("speaking");
		expect(sampleRunAt(SAMPLE_TIMING.userSpeaksAt + 100).call.state).toBe("listening");
	});

	test("while Laptop B wakes, A is already online and the wake step shows its tool and progress", () => {
		const run = scene("waking");
		const wakeB = run.steps.find((s) => s.id === "wake-b");

		expect(stateOf(run, "wake-a")).toBe("done");
		expect(wakeB?.state).toBe("executing");
		expect(wakeB?.tool).toEqual({ name: "wakeDevice", args: { device: "laptop-b" } });
		expect(wakeB?.progress).toBeGreaterThan(0);
		expect(wakeB?.progress).toBeLessThan(1);
		expect(deviceState(run, "laptop-a")).toBe("online");
		expect(deviceState(run, "laptop-b")).toBe("waking");
	});

	test("only one step is executing at any moment of the run", () => {
		for (let t = 0; t <= SAMPLE_TIMING.allStepsDoneAt + 2000; t += 250) {
			const executing = sampleRunAt(t).steps.filter((s) => s.state === "executing");
			expect(executing.length).toBeLessThanOrEqual(1);
		}
	});

	test("the file's hash appears only once the file has reached Laptop B", () => {
		const hash = (t: number) => sampleRunAt(t).evidence.find((e) => e.id === "file-hash")?.value;
		const sent = sampleRunAt(SAMPLE_TIMING.allStepsDoneAt).steps.find((s) => s.id === "send-file");

		expect(hash(SAMPLE_TIMING.taskStartsAt)).toBeNull();
		expect(sent?.state).toBe("done");
		expect(hash(SAMPLE_TIMING.allStepsDoneAt)).toMatch(/^[0-9a-f]{4}…[0-9a-f]{4}$/);
	});

	test("subtitles show only the last two lines", () => {
		expect(sampleRunAt(SAMPLE_TIMING.allStepsDoneAt).call.subtitles.length).toBeLessThanOrEqual(2);
	});
});

describe("at the end", () => {
	test("after the result is opened on Laptop A, the last step waits for the user and the assistant asks", () => {
		const run = scene("confirm");

		expect(stateOf(run, "open")).toBe("needs-you");
		expect(run.task.state).toBe("needs-you");
		expect(run.call.subtitles.at(-1)?.text).toMatch(/confirm/i);
	});

	test("confirming finishes the task", () => {
		const run = sampleRunAt(SAMPLE_TIMING.allStepsDoneAt + 5000, { decision: "confirmed" });

		expect(run.task.state).toBe("done");
		expect(run.steps.every((s) => s.state === "done")).toBe(true);
	});

	test("cancelling ends the task without marking the last step done", () => {
		const run = sampleRunAt(SAMPLE_TIMING.allStepsDoneAt + 5000, { decision: "cancelled" });

		expect(run.task.state).toBe("cancelled");
		expect(stateOf(run, "open")).toBe("cancelled");
	});

	test("hanging up ends the call but the devices keep working on the task", () => {
		const t = SAMPLE_TIMING.allStepsDoneAt - 1000;
		const run = sampleRunAt(t, { hungUpAt: SAMPLE_TIMING.taskStartsAt + 1000 });

		expect(run.call.state).toBe("ended");
		expect(run.steps.some((s) => s.state === "executing" || s.state === "done")).toBe(true);
	});
});

test("every named scene resolves to a run", () => {
	for (const name of SCENES) {
		expect(scene(name).steps).toHaveLength(5);
	}
	expect(scene("idle").call.state).toBe("idle");
	expect(scene("done").task.state).toBe("done");
});
