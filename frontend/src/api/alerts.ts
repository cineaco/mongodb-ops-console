import client from "./client";

export interface Alert {
  id: string;
  cluster_id: string;
  metric: string;
  severity: string;
  message: string;
  threshold_value: number;
  actual_value: number;
  status: string;
  first_triggered_at: string;
  last_triggered_at: string;
  resolved_at: string | null;
  notified_at: string | null;
  created_by: string;
}

export async function fetchClusterAlerts(clusterId: string, status?: string): Promise<Alert[]> {
  return (await client.get<Alert[]>(`/clusters/${clusterId}/alerts`, { params: { status } })).data;
}

export async function resolveAlert(clusterId: string, alertId: string): Promise<Alert> {
  return (await client.patch<Alert>(`/clusters/${clusterId}/alerts/${alertId}`)).data;
}

export async function fetchAllAlerts(params?: { status?: string; limit?: number }): Promise<Alert[]> {
  return (await client.get<Alert[]>("/alerts", { params })).data;
}

export async function fetchActiveAlertCount(): Promise<number> {
  const resp = await client.get<{ active_count: number }>("/alerts/count");
  return resp.data.active_count;
}
