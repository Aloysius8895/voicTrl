import { Check } from "lucide-react";

import type { StepState, TaskState } from "../demo/sampleRun";
import { STEP_LABEL, TASK_LABEL, type Tone } from "./labels";

function Chip({ label, tone }: { label: string; tone: Tone }) {
	return (
		<span className="chip" data-tone={tone}>
			{tone === "good" ? (
				<Check className="chip__check" size={12} strokeWidth={3} aria-hidden />
			) : (
				<i className="chip__dot" aria-hidden />
			)}
			{label}
		</span>
	);
}

export const StepChip = ({ state }: { state: StepState }) => <Chip label={STEP_LABEL[state][0]} tone={STEP_LABEL[state][1]} />;
export const TaskChip = ({ state }: { state: TaskState }) => <Chip label={TASK_LABEL[state][0]} tone={TASK_LABEL[state][1]} />;
