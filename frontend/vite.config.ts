import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // Read VITE_* variables from the repository-root .env so there is one env file for the whole repo.
  envDir: "..",
  server: { port: 5173, strictPort: true },
});
