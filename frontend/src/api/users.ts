import client from "./client";

export interface User {
  id: string;
  username: string;
  email: string | null;
  role: string;
  disabled: boolean;
  created_at: string;
  last_login_at: string | null;
}

export async function fetchUsers(): Promise<User[]> {
  return (await client.get<User[]>("/users")).data;
}

export async function createUser(data: {
  username: string;
  password: string;
  role: string;
  email?: string;
}): Promise<User> {
  return (await client.post<User>("/users", data)).data;
}

export async function updateUser(
  id: string,
  data: { role?: string; disabled?: boolean; password?: string },
): Promise<User> {
  return (await client.patch<User>(`/users/${id}`, data)).data;
}

export async function deleteUser(id: string): Promise<void> {
  await client.delete(`/users/${id}`);
}
