import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base: the page works at the Pages sub-path and when served from any folder.
export default defineConfig({ base: "./", plugins: [react()] });
