import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  basePath: "/transformer",
  async redirects() {
    return [
      {
        source: "/workbench",
        destination: "/workbench/rules",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
