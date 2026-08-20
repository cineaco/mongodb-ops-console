import client from "./client";

export interface Job {
  job_id: string;
  cluster_id: string;
  operation: string;
  status: string;
  parameters: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  created_by: string;
}

export interface JobCreated {
  job_id: string;
  operation: string;
  status: string;
  created_at: string;
}

/* ── Queries ── */

export async function getJob(clusterId: string, jobId: string): Promise<Job> {
  return (await client.get<Job>(`/clusters/${clusterId}/jobs/${jobId}`)).data;
}

export async function listClusterJobs(clusterId: string): Promise<Job[]> {
  return (await client.get<Job[]>(`/clusters/${clusterId}/jobs`)).data;
}

export async function cancelJob(
  clusterId: string,
  jobId: string,
): Promise<Job> {
  return (await client.post<Job>(`/clusters/${clusterId}/jobs/${jobId}/cancel`))
    .data;
}

/* ── Trigger helpers ── */

function triggerOp(
  clusterId: string,
  op: string,
  body?: Record<string, unknown>,
): Promise<JobCreated> {
  return client
    .post<JobCreated>(`/clusters/${clusterId}/ops/${op}`, body ?? {})
    .then((r) => r.data);
}

export function triggerRestartNode(
  clusterId: string,
  host: string,
): Promise<JobCreated> {
  return triggerOp(clusterId, "restart_node", { host });
}

export function triggerRollingRestart(clusterId: string): Promise<JobCreated> {
  return triggerOp(clusterId, "rolling_restart");
}

export function triggerRotatePassword(
  clusterId: string,
  secretId: string,
): Promise<JobCreated> {
  return triggerOp(clusterId, "rotate_password", { secret_id: secretId });
}

export function triggerCreateUser(
  clusterId: string,
  data: {
    database: string;
    username: string;
    password_secret_id: string;
    roles: string;
  },
): Promise<JobCreated> {
  return triggerOp(clusterId, "create_app_user", data);
}

export function triggerDeleteUser(
  clusterId: string,
  data: { database: string; username: string },
): Promise<JobCreated> {
  return triggerOp(clusterId, "delete_app_user", data);
}

export function triggerPbmBackup(clusterId: string): Promise<JobCreated> {
  return triggerOp(clusterId, "pbm_backup");
}

export function triggerPbmRestore(
  clusterId: string,
  timestamp: string,
): Promise<JobCreated> {
  return triggerOp(clusterId, "pbm_restore", { timestamp });
}

export function triggerPbmList(clusterId: string): Promise<JobCreated> {
  return triggerOp(clusterId, "pbm_list");
}

export function triggerMongodumpS3(
  clusterId: string,
  data: {
    s3_bucket: string;
    s3_prefix: string;
    s3_region: string;
    auth_method: string;
    s3_credential_secret_id?: string;
  },
): Promise<JobCreated> {
  return triggerOp(clusterId, "mongodump_s3", data);
}

export function triggerDeploy(
  clusterId: string,
  tags?: string[],
): Promise<JobCreated> {
  return triggerOp(clusterId, "deploy", {
    tags: tags ?? ["install", "config", "replication", "security", "summary"],
  });
}

export function triggerRerun(
  clusterId: string,
  tags: string[],
): Promise<JobCreated> {
  return triggerOp(clusterId, "rerun", { tags });
}
