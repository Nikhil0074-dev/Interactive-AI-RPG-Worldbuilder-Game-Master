/** Proxy /api to the FastAPI backend so the browser never needs CORS or the backend URL. */
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
module.exports = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
