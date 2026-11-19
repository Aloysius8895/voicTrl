import { Laptop, Smartphone, Watch } from "lucide-react";
import { useState } from "react";

import type { Device, Run } from "../demo/sampleRun";
import { DEVICE_LABEL } from "./labels";

type Tab = "devices" | "evidence";

const ICON = { laptop: Laptop, watch: Watch, phone: Smartphone } as const;

function DeviceTile({ device }: { device: Device }) {
	const Icon = ICON[device.kind];
	const [label, tone] = DEVICE_LABEL[device.state];
	return (
		<div className="tile" data-tone={tone}>
			<p className="tile__label">
				<Icon size={15} aria-hidden />
				{device.name}
			</p>
			<p className="tile__value">
				<i className="tile__dot" aria-hidden />
				{label}
			</p>
			<p className="tile__detail">{device.detail}</p>
		</div>
	);
}

function initialTab(): Tab {
	return new URLSearchParams(window.location.search).get("tab") === "evidence" ? "evidence" : "devices";
}

export function DevicePanel({ run }: { run: Run }) {
	const [tab, setTab] = useState<Tab>(initialTab);
	const waiting = run.task.state === "needs-you" ? 1 : 0;
	const proven = run.evidence.filter((e) => e.value !== null).length;

	return (
		<section className="devices" id="devices" aria-label="Devices">
			<header className="panel-head">
				<p className="eyebrow">
					<i aria-hidden />
					Devices
				</p>
			</header>
			<h2 className="devices__title">Every device, live.</h2>

			<div className="console">
				<div className="console__bar">
					<span className="wordmark wordmark--small">voicTrl</span>
					<span className="console__label">Your devices</span>
					<span className="console__badge" data-on={waiting > 0 || undefined}>
						Needs you <b>{waiting}</b>
					</span>
				</div>

				<div className="tabs" role="tablist" aria-label="Device view">
					<button type="button" role="tab" aria-selected={tab === "devices"} onClick={() => setTab("devices")}>
						Devices
					</button>
					<button type="button" role="tab" aria-selected={tab === "evidence"} onClick={() => setTab("evidence")}>
						Evidence <span className="tabs__count">{proven}/4</span>
					</button>
				</div>

				{tab === "devices" ? (
					<div className="tiles" role="tabpanel" aria-label="Devices">
						{run.devices.map((d) => (
							<DeviceTile key={d.id} device={d} />
						))}
					</div>
				) : (
					<div className="tiles" role="tabpanel" aria-label="Evidence">
						{run.evidence.map((e) => (
							<div key={e.id} className="tile tile--evidence" data-empty={e.value === null || undefined}>
								<p className="tile__label">{e.label}</p>
								<p className={e.code ? "tile__value tile__value--mono" : "tile__value"}>{e.value ?? "—"}</p>
								<p className="tile__detail">{e.value === null ? "Not yet" : e.detail}</p>
							</div>
						))}
					</div>
				)}
			</div>
		</section>
	);
}
