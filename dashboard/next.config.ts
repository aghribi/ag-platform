import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle so the container image only needs the
  // runtime deps, not the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
