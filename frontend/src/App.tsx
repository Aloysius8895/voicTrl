import { Phone } from "lucide-react";

import { CallCard } from "./components/CallCard";
import { DevicePanel } from "./components/DevicePanel";
import { TaskPanel } from "./components/TaskPanel";
import { useSampleRun } from "./demo/useSampleRun";

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

export default function App() {
	const controls = useSampleRun();
	const { run } = controls;
	const live = run.call.state !== "idle" && run.call.state !== "ended";

	const startCall = () => {
		controls.call();
		document.getElementById("call")?.scrollIntoView({ behavior: "smooth", block: "start" });
	};

	return (
		<div className="app">
			<header className="topbar">
				<nav className="topbar__inner" aria-label="Main">
					<span className="wordmark">voicTrl</span>
					<div className="topbar__links">
						<a href="#call">Call</a>
						<a href="#task">Task</a>
						<a href="#devices">Devices</a>
					</div>
					{live ? (
						<a className="pill pill--orange pill--small" href="#call">
							<i className="pulse" aria-hidden />
							On call · {clock(run.call.seconds)}
						</a>
					) : (
						<button type="button" className="pill pill--orange pill--small" onClick={startCall}>
							<Phone size={16} aria-hidden />
							Call
						</button>
					)}
				</nav>
			</header>

			<section className="hero">
				<h1 className="hero__title">
					One voice.
					<br />
					<span>Every device.</span>
				</h1>
				<p className="hero__text">
					Talk to your assistant. It wakes your laptops, moves the files, has Claude build the page, and opens the
					result wherever you are.
				</p>
			</section>

			<main className="board">
				<CallCard run={run} controls={controls} />
				<TaskPanel run={run} controls={controls} />
				<DevicePanel run={run} />
			</main>

			<footer className="foot">Sample mode · example data, nothing is sent to your devices.</footer>
		</div>
	);
}
