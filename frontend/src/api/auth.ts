import client, { setAccessToken } from "./client";

export interface LoginResponse { access_token: string; refresh_token: string; token_type: string; }
export interface UserMe { id: string; username: string; email: string | null; role: string; disabled: boolean; }

export async function login(username: string, password: string): Promise<LoginResponse> {
  const resp = await client.post<LoginResponse>("/auth/login", { username, password });
  setAccessToken(resp.data.access_token);
  localStorage.setItem("refresh_token", resp.data.refresh_token);
  return resp.data;
}

export async function fetchMe(): Promise<UserMe> {
  const resp = await client.get<UserMe>("/auth/me");
  return resp.data;
}

export async function logout(): Promise<void> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (refreshToken) await client.post("/auth/logout", { refresh_token: refreshToken }).catch(() => {});
  setAccessToken(null);
  localStorage.removeItem("refresh_token");
}
