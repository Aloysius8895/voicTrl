import { CircleCheck, LoaderCircle, MessageSquareText } from "lucide-react";

import type { Run, Step } from "../demo/sampleRun";
import type { SampleControls } from "../demo/useSampleRun";
import { StepChip, TaskChip } from "./StatusChip";

const pad = (n: number) => String(n).padStart(2, "0");

function ToolChip({ step }: { step: Step }) {
	return (
		<div className="tool">
			<code className="tool__name">{step.tool.name}</code>
			{Object.entries(step.tool.args).map(([k, v]) => (
				<code key={k} className="tool__arg">
					{k}: {v}
				</code>
			))}
		</div>
	);
}

function StepDetail({ step }: { step: Step }) {
	return (
		<ol className="trace">
			<li className="trace__item" data-done>
				<CircleCheck className="trace__icon" size={18} aria-hidden />
				<div>
					<p className="trace__title">Understand</p>
					<p className="trace__text">{step.reason}</p>
				</div>
			</li>
			<li className="trace__item" data-done>
				<CircleCheck className="trace__icon" size={18} aria-hidden />
				<div>
					<p className="trace__title">Pick the tool</p>
					<ToolChip step={step} />
				</div>
			</li>
			<li className="trace__item">
				<LoaderCircle className="trace__icon trace__icon--spin" size={18} aria-hidden />
				<div className="trace__grow">
					<p className="trace__title">Execute</p>
					<p className="trace__text trace__text--small">{step.how}</p>
					<div
						className="bar"
						role="progressbar"
						aria-valuemin={0}
						aria-valuemax={100}
						aria-valuenow={Math.round(step.progress * 100)}
						aria-label={`${step.title} progress`}
					>
						<span style={{ transform: `scaleX(${step.progress})` }} />
					</div>
				</div>
			</li>
		</ol>
	);
}

function StepCard({ step, index, total, controls }: { step: Step; index: number; total: number; controls: SampleControls }) {
	const finished = step.state === "done";
	return (
		<li className="step" data-state={step.state}>
			<div className="step__row">
				<div className="step__head">
					<p className="step__num">
						<b>{pad(index + 1)}</b> / {pad(total)}
					</p>
					<h3 className="step__title">{step.title}</h3>
					<p className="step__sum">{finished ? step.result : step.summary}</p>
				</div>
				<StepChip state={step.state} />
			</div>

			{step.state === "executing" && <StepDetail step={step} />}

			{step.state === "needs-you" && (
				<div className="ask">
					<p className="ask__text">
						<MessageSquareText size={18} aria-hidden />
						The page is open on Laptop A. Does it look right?
					</p>
					<div className="ask__actions">
						<button type="button" className="pill pill--orange" onClick={controls.confirm}>
							Confirm
						</button>
						<button type="button" className="pill pill--ghost" onClick={controls.cancel}>
							Cancel
						</button>
					</div>
					<p className="ask__hint">Or just say “confirm”.</p>
				</div>
			)}
		</li>
	);
}

export function TaskPanel({ run, controls }: { run: Run; controls: SampleControls }) {
	const started = run.task.state !== "not-started";
	return (
		<section className="task" id="task" aria-label="Current task">
			<header className="panel-head">
				<p className="eyebrow">
					<i aria-hidden />
					Current task
				</p>
				<TaskChip state={run.task.state} />
			</header>

			{started ? (
				<>
					<h2 className="task__title">{run.task.title}</h2>
					<ol className="steps">
						{run.steps.map((step, i) => (
							<StepCard key={step.id} step={step} index={i} total={run.steps.length} controls={controls} />
						))}
					</ol>
				</>
			) : (
				<div className="empty">
					<h2 className="task__title">Nothing running yet.</h2>
					<p className="empty__text">Call your assistant and ask for something, for example:</p>
					<p className="empty__quote">“Wake laptop A and B, send file one to B, build the page there and show me on A.”</p>
					<p className="empty__text">Each step shows up here as it happens.</p>
				</div>
			)}
		</section>
	);
}
