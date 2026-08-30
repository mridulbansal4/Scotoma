/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Every screen reads committed artefacts from disk at build time. There is no runtime
  // data source, so image optimisation and remote patterns have nothing to fetch.
  images: { unoptimized: true },
};

export default nextConfig;
