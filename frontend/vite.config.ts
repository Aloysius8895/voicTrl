import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
	plugins: [
		react(),
		VitePWA({
			registerType: "autoUpdate",
			includeAssets: ["favicon.ico", "logo.svg", "apple-touch-icon-180x180.png"],
			manifest: {
				name: "voicTrl",
				short_name: "voicTrl",
				description: "Talk to your assistant and watch it work across your devices.",
				theme_color: "#f5f1ed",
				background_color: "#f5f1ed",
				display: "standalone",
				orientation: "portrait",
				start_url: "/",
				icons: [
					{ src: "pwa-64x64.png", sizes: "64x64", type: "image/png" },
					{ src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
					{ src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
					{ src: "maskable-icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
				],
			},
		}),
	],
	server: { port: 5310, strictPort: true },
	preview: { port: 5310, strictPort: true },
});
