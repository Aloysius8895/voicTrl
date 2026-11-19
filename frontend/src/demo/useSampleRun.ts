// Drives the sample run in the browser: a clock, plus what the user has pressed.
// `?scene=<name>` freezes the page at a fixed moment (for screenshots);
// add `&play=1` to keep running from there.
import { useCallback, useEffect, useMemo, useState } from "react";

import { type Decision, type Run, SCENES, type SceneName, sampleRunAt, sceneTime } from "./sampleRun";

const TICK_MS = 100;

function sceneFromUrl(): { scene: SceneName | null; play: boolean } {
	const params = new URLSearchParams(window.location.search);
	const name = params.get("scene");
	const scene = SCENES.includes(name as SceneName) ? (name as SceneName) : null;
	return { scene, play: params.get("play") === "1" };
}

export interface SampleControls {
	run: Run;
	muted: boolean;
	/** True once a call has been started at least once. */
	started: boolean;
	call(): void;
	hangUp(): void;
	toggleMute(): void;
	confirm(): void;
	cancel(): void;
	restart(): void;
}

export function useSampleRun(): SampleControls {
	const initial = useMemo(() => sceneFromUrl(), []);
	const frozen = initial.scene !== null && !initial.play;
	const start = initial.scene ? sceneTime(initial.scene) : { t: null, choices: {} };

	const [startedAt, setStartedAt] = useState<number | null>(() =>
		start.t === null ? null : performance.now() - start.t,
	);
	const [now, setNow] = useState(() => performance.now());
	const [decision, setDecision] = useState<Decision | undefined>(start.choices.decision);
	const [hungUpAt, setHungUpAt] = useState<number | undefined>(undefined);
	const [muted, setMuted] = useState(false);

	useEffect(() => {
		if (startedAt === null || frozen) return;
		const id = window.setInterval(() => setNow(performance.now()), TICK_MS);
		return () => window.clearInterval(id);
	}, [startedAt, frozen]);

	const elapsed = startedAt === null ? null : Math.max(0, now - startedAt);
	const run = useMemo(() => sampleRunAt(elapsed, { decision, hungUpAt }), [elapsed, decision, hungUpAt]);

	const call = useCallback(() => {
		if (startedAt !== null) {
			setHungUpAt(undefined); // call again: the run on the devices carried on meanwhile
			return;
		}
		const t = performance.now();
		setStartedAt(t);
		setNow(t);
	}, [startedAt]);

	const restart = useCallback(() => {
		const t = performance.now();
		setDecision(undefined);
		setHungUpAt(undefined);
		setMuted(false);
		setStartedAt(t);
		setNow(t);
	}, []);

	return {
		run,
		muted,
		started: startedAt !== null,
		call,
		restart,
		hangUp: () => setHungUpAt(elapsed ?? 0),
		toggleMute: () => setMuted((m) => !m),
		confirm: () => run.task.state === "needs-you" && setDecision("confirmed"),
		cancel: () => run.task.state === "needs-you" && setDecision("cancelled"),
	};
}
