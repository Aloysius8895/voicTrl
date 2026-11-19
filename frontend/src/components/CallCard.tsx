import { Mic, MicOff, Phone, PhoneOff, RotateCcw } from "lucide-react";

import type { CallState, Run } from "../demo/sampleRun";
import type { SampleControls } from "../demo/useSampleRun";

const STATUS: Record<CallState, string> = {
	idle: "Ready when you are",
	connecting: "Connecting…",
	listening: "Listening",
	thinking: "Thinking",
	speaking: "Speaking",
	ended: "Call ended",
};

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

function Orb({ state, muted }: { state: CallState; muted: boolean }) {
	return (
		<div className="orb" data-state={state} data-muted={muted || undefined} aria-hidden>
			<span className="orb__ring orb__ring--1" />
			<span className="orb__ring orb__ring--2" />
			<span className="orb__ring orb__ring--3" />
			<span className="orb__core">
				{state === "speaking" ? (
					<span className="orb__bars">
						<i />
						<i />
						<i />
						<i />
						<i />
					</span>
				) : state === "thinking" || state === "connecting" ? (
					<span className="orb__dots">
						<i />
						<i />
						<i />
					</span>
				) : state === "idle" || state === "ended" ? (
					<Phone size={30} strokeWidth={1.8} />
				) : muted ? (
					<MicOff size={30} strokeWidth={1.8} />
				) : (
					<Mic size={30} strokeWidth={1.8} />
				)}
			</span>
		</div>
	);
}

export function CallCard({ run, controls }: { run: Run; controls: SampleControls }) {
	const { state, subtitles, seconds } = run.call;
	const live = state !== "idle" && state !== "ended";
	const taskOver = run.task.state === "done" || run.task.state === "cancelled";

	return (
		<section className="call" id="call" data-state={state} aria-label="Call with your assistant">
			<div className="call__top">
				<span className="call__live" data-live={live || undefined}>
					<i aria-hidden />
					{live ? `Live · ${clock(seconds)}` : state === "ended" ? "Call ended" : "Ready"}
				</span>
				<span className="call__sample" title="Example data. Nothing is sent to your devices.">
					Sample
				</span>
			</div>

			<div className="call__stage">
				<Orb state={state} muted={controls.muted} />
			</div>

			<div className="call__who">
				<h2 className="call__name">Assistant</h2>
				<p className="call__status" aria-live="polite">
					{controls.muted && live ? "Muted" : STATUS[state]}
				</p>
			</div>

			<div className="call__subs" aria-live="polite">
				{subtitles.length === 0 ? (
					<p className="call__hint">
						{state === "ended"
							? "Your devices keep working on the task."
							: "Say what your devices should do. Your watch can hear you too."}
					</p>
				) : (
					subtitles.map((line, i) => (
						<p key={`${i}-${line.text}`} className="sub" data-speaker={line.speaker}>
							<span className="sub__who">{line.speaker === "you" ? "You" : "Assistant"}</span>
							<span className="sub__text">{line.text}</span>
						</p>
					))
				)}
			</div>

			<div className="call__controls">
				{live ? (
					<>
						<button
							type="button"
							className="round round--soft"
							onClick={controls.toggleMute}
							aria-pressed={controls.muted}
							aria-label={controls.muted ? "Unmute" : "Mute"}
						>
							{controls.muted ? <MicOff size={22} /> : <Mic size={22} />}
						</button>
						<button type="button" className="round round--end" onClick={controls.hangUp} aria-label="Hang up">
							<PhoneOff size={24} />
						</button>
					</>
				) : (
					<>
						<button type="button" className="pill pill--white" onClick={controls.call}>
							<Phone size={18} aria-hidden />
							{state === "ended" ? "Call again" : "Call your assistant"}
						</button>
						{state === "ended" && taskOver && (
							<button type="button" className="round round--soft" onClick={controls.restart} aria-label="Run the sample again">
								<RotateCcw size={20} />
							</button>
						)}
					</>
				)}
			</div>
		</section>
	);
}
