import client from "./client";

export interface OpsPerSecond {
  insert: number | null;
  query: number | null;
  update: number | null;
  delete: number | null;
}

export interface MetricLatest {
  cluster_id: string;
  collected_at: string;
  rs_state: string;
  primary_member: string | null;
  members_up: number;
  members_total: number;
  max_replication_lag_seconds: number | null;
  connections: { current: number | null; available: number | null };
  ops_per_second: OpsPerSecond;
  memory: { resident_mb: number | null; virtual_mb: number | null };
  cache: { used_bytes: number | null; total_bytes: number | null; dirty_bytes: number | null; hit_ratio: number | null };
  storage: { data_size_bytes: number | null; fs_total_bytes: number | null; fs_used_bytes: number | null; fs_used_percent: number | null };
  status: string;
}

export interface MetricPoint {
  collected_at: string;
  connections_current: number | null;
  max_replication_lag_seconds: number | null;
  memory_resident_mb: number | null;
  fs_used_percent: number | null;
  ops_per_second: OpsPerSecond;
}

export interface MetricRange {
  cluster_id: string;
  range: string;
  points: MetricPoint[];
}

export async function fetchLatestMetrics(clusterId: string): Promise<MetricLatest> {
  return (await client.get<MetricLatest>(`/clusters/${clusterId}/metrics/latest`)).data;
}

export async function fetchMetricsRange(clusterId: string, range: string): Promise<MetricRange> {
  return (await client.get<MetricRange>(`/clusters/${clusterId}/metrics`, { params: { range } })).data;
}

export async function refreshMetrics(clusterId: string): Promise<MetricLatest> {
  return (await client.post<MetricLatest>(`/clusters/${clusterId}/metrics/refresh`)).data;
}
