import axios from "axios";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) { accessToken = token; }
export function getAccessToken() { return accessToken; }

const client = axios.create({ baseURL: "/api", headers: { "Content-Type": "application/json" } });

client.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) throw new Error("No refresh token");
        const resp = await axios.post("/api/auth/refresh", { refresh_token: refreshToken });
        setAccessToken(resp.data.access_token);
        localStorage.setItem("refresh_token", resp.data.refresh_token);
        original.headers.Authorization = `Bearer ${resp.data.access_token}`;
        return client(original);
      } catch {
        setAccessToken(null);
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default client;
