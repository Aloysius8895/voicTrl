import type { DeviceState, StepState, TaskState } from "../demo/sampleRun";

export type Tone = "idle" | "live" | "good" | "warn" | "ask" | "bad";

export const STEP_LABEL: Record<StepState, [string, Tone]> = {
	waiting: ["Waiting", "idle"],
	executing: ["Executing", "live"],
	done: ["Done", "good"],
	"needs-you": ["Needs you", "ask"],
	cancelled: ["Cancelled", "idle"],
	failed: ["Failed", "bad"],
};

export const TASK_LABEL: Record<TaskState, [string, Tone]> = {
	"not-started": ["No task", "idle"],
	running: ["Running", "live"],
	"needs-you": ["Needs you", "ask"],
	done: ["Done", "good"],
	cancelled: ["Cancelled", "idle"],
};

export const DEVICE_LABEL: Record<DeviceState, [string, Tone]> = {
	asleep: ["Asleep", "idle"],
	waking: ["Waking", "warn"],
	online: ["Online", "good"],
	offline: ["Offline", "bad"],
};
