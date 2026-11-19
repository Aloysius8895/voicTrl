import { defineConfig, minimal2023Preset } from "@vite-pwa/assets-generator/config";

// Generates favicon.ico, the PWA icons and the Apple touch icon from public/logo.svg.
export default defineConfig({
	headLinkOptions: { preset: "2023" },
	preset: { ...minimal2023Preset, maskable: { ...minimal2023Preset.maskable, resizeOptions: { background: "#ff6a2a" } }, apple: { ...minimal2023Preset.apple, resizeOptions: { background: "#ff6a2a" } } },
	images: ["public/logo.svg"],
});
