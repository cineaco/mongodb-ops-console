import client from "./client";

export interface Cluster {
  id: string;
  name: string;
  description: string | null;
  topology: string;
  mongodb_version: string;
  mongodb_port: number;
  replicaset_name: string;
  config: Record<string, unknown>;
  status: string;
  admin_credentials_secret_id: string | null;
  last_deployed_at: string | null;
  last_deployed_by: string | null;
  created_at: string;
  created_by: string;
}

export async function fetchClusters(): Promise<Cluster[]> {
  return (await client.get<Cluster[]>("/clusters")).data;
}

export async function createCluster(data: {
  name: string;
  topology: string;
  mongodb_version: string;
  mongodb_port?: number;
  replicaset_name?: string;
  config?: Record<string, unknown>;
  description?: string;
}): Promise<Cluster> {
  return (await client.post<Cluster>("/clusters", data)).data;
}

export async function deleteCluster(id: string): Promise<void> {
  await client.delete(`/clusters/${id}`);
}
