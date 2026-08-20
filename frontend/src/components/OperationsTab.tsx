import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listClusterJobs, type Job } from "../api/jobs";
import { useAuth } from "../hooks/useAuth";
import JobStatusBadge from "./JobStatusBadge";
import OperationModal from "./OperationModal";

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };

interface OpCard {
  key: string;
  name: string;
  description: string;
  minRole: string;
}

const OPERATIONS: OpCard[] = [
  {
    key: "restart_node",
    name: "Restart Node",
    description: "Restart a single mongod",
    minRole: "operator",
  },
  {
    key: "rolling_restart",
    name: "Rolling Restart",
    description: "Restart all nodes sequentially",
    minRole: "admin",
  },
  {
    key: "rotate_password",
    name: "Rotate Password",
    description: "Change admin password",
    minRole: "admin",
  },
  {
    key: "create_app_user",
    name: "Create User",
    description: "Create application DB user",
    minRole: "operator",
  },
  {
    key: "delete_app_user",
    name: "Delete User",
    description: "Remove application DB user",
    minRole: "operator",
  },
  {
    key: "pbm_backup",
    name: "PBM Backup",
    description: "Trigger Percona backup",
    minRole: "operator",
  },
  {
    key: "pbm_restore",
    name: "PBM Restore",
    description: "Restore from PBM backup",
    minRole: "admin",
  },
  {
    key: "pbm_list",
    name: "PBM List",
    description: "List available backups",
    minRole: "operator",
  },
  {
    key: "mongodump_s3",
    name: "Dump to S3",
    description: "mongodump archive to S3",
    minRole: "operator",
  },
  {
    key: "rerun",
    name: "Re-run Playbook",
    description: "Re-run with selected tags",
    minRole: "admin",
  },
];

const ROLE_BADGE_COLORS: Record<string, string> = {
  admin: "bg-purple-100 text-purple-700",
  operator: "bg-blue-100 text-blue-700",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function duration(job: Job): string {
  if (!job.started_at) return "-";
  const start = new Date(job.started_at).getTime();
  const end = job.finished_at
    ? new Date(job.finished_at).getTime()
    : Date.now();
  const secs = Math.round((end - start) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

interface Props {
  clusterId: string;
  hosts?: string[];
}

export default function OperationsTab({ clusterId, hosts = [] }: Props) {
  const { user } = useAuth();
  const userLevel = ROLE_LEVEL[user?.role ?? ""] ?? 0;
  const [activeOp, setActiveOp] = useState<string | null>(null);

  const {
    data: jobs = [],
    isLoading,
    error,
  } = useQuery<Job[]>({
    queryKey: ["cluster-jobs", clusterId],
    queryFn: () => listClusterJobs(clusterId),
    refetchInterval: 5000,
  });

  const visibleOps = OPERATIONS.filter(
    (op) => userLevel >= (ROLE_LEVEL[op.minRole] ?? 99),
  );

  return (
    <div className="space-y-8">
      {/* ── Action Cards ── */}
      {visibleOps.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Actions
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visibleOps.map((op) => (
              <button
                key={op.key}
                onClick={() => setActiveOp(op.key)}
                className="flex flex-col items-start rounded-lg border bg-white p-4 text-left shadow-sm transition hover:border-blue-400 hover:shadow"
              >
                <div className="flex w-full items-center justify-between">
                  <span className="font-medium text-gray-900">{op.name}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      ROLE_BADGE_COLORS[op.minRole] ??
                      "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {op.minRole}
                  </span>
                </div>
                <span className="mt-1 text-sm text-gray-500">
                  {op.description}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Recent Jobs Table ── */}
      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Recent Jobs
        </h3>

        {isLoading && <p className="text-gray-500">Loading jobs...</p>}
        {error && (
          <p className="text-red-600">
            Failed to load jobs: {(error as Error).message}
          </p>
        )}

        {!isLoading && !error && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-3 py-2 border-b font-medium">Operation</th>
                  <th className="px-3 py-2 border-b font-medium">Status</th>
                  <th className="px-3 py-2 border-b font-medium">Started</th>
                  <th className="px-3 py-2 border-b font-medium">Duration</th>
                  <th className="px-3 py-2 border-b font-medium">User</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-6 text-center text-gray-400"
                    >
                      No jobs yet.
                    </td>
                  </tr>
                ) : (
                  jobs.map((j) => (
                    <tr key={j.job_id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 border-b font-mono text-xs">
                        {j.operation}
                      </td>
                      <td className="px-3 py-2 border-b">
                        <JobStatusBadge status={j.status} />
                      </td>
                      <td className="px-3 py-2 border-b text-gray-500">
                        {j.started_at ? formatDate(j.started_at) : "-"}
                      </td>
                      <td className="px-3 py-2 border-b text-gray-500">
                        {duration(j)}
                      </td>
                      <td className="px-3 py-2 border-b text-gray-500">
                        {j.created_by}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Modal ── */}
      {activeOp && (
        <OperationModal
          clusterId={clusterId}
          operation={activeOp}
          onClose={() => setActiveOp(null)}
          hosts={hosts}
        />
      )}
    </div>
  );
}
