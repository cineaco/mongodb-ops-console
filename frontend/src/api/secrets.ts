import client from "./client";

export interface Secret {
  id: string;
  name: string;
  type: string;
  created_at: string;
  created_by: string;
}

export async function fetchSecrets(): Promise<Secret[]> {
  return (await client.get<Secret[]>("/secrets")).data;
}

export async function createSecret(data: {
  name: string;
  type: string;
  plaintext: string;
}): Promise<Secret> {
  return (await client.post<Secret>("/secrets", data)).data;
}

export async function deleteSecret(id: string): Promise<void> {
  await client.delete(`/secrets/${id}`);
}
