import client from "./client";

export interface AuditLog {
  id: number;
  user_id: string | null;
  username: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  occurred_at: string;
}

export async function fetchAuditLogs(params?: {
  limit?: number;
  cursor?: number;
  action?: string;
  resource_type?: string;
}): Promise<AuditLog[]> {
  return (await client.get<AuditLog[]>("/audit-logs", { params })).data;
}
