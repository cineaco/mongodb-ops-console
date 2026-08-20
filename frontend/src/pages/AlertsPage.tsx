import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAllAlerts, resolveAlert, type Alert } from "../api/alerts";
import { useAuth } from "../hooks/useAuth";

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  warning: "bg-yellow-100 text-yellow-800",
};

function SeverityBadge({ severity }: { severity: string }) {
  const color = SEVERITY_COLORS[severity] ?? "bg-gray-100 text-gray-800";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${color}`}>
      {severity}
    </span>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) + "..." : id;
}

export default function AlertsPage() {
  const [filter, setFilter] = useState<string>("active");
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userLevel = ROLE_LEVEL[user?.role ?? ""] ?? 0;

  const statusParam = filter === "all" ? undefined : filter;

  const { data: alerts = [], isLoading, error } = useQuery<Alert[]>({
    queryKey: ["all-alerts", statusParam],
    queryFn: () => fetchAllAlerts({ status: statusParam, limit: 100 }),
    refetchInterval: 30000,
  });

  const resolveMut = useMutation({
    mutationFn: ({ clusterId, alertId }: { clusterId: string; alertId: string }) =>
      resolveAlert(clusterId, alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["all-alerts"] });
      queryClient.invalidateQueries({ queryKey: ["active-alert-count"] });
    },
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Alerts</h1>
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-600">Filter:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm"
          >
            <option value="active">Active</option>
            <option value="resolved">Resolved</option>
            <option value="all">All</option>
          </select>
        </div>
      </div>

      {isLoading && <p className="text-gray-500">Loading alerts...</p>}
      {error && <p className="text-red-600">Failed to load alerts: {(error as Error).message}</p>}

      {!isLoading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-3 py-2 border-b font-medium">Severity</th>
                <th className="px-3 py-2 border-b font-medium">Cluster ID</th>
                <th className="px-3 py-2 border-b font-medium">Metric</th>
                <th className="px-3 py-2 border-b font-medium">Message</th>
                <th className="px-3 py-2 border-b font-medium">Value</th>
                <th className="px-3 py-2 border-b font-medium">Status</th>
                <th className="px-3 py-2 border-b font-medium">Last Triggered</th>
                {userLevel >= ROLE_LEVEL.operator && (
                  <th className="px-3 py-2 border-b font-medium">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {alerts.length === 0 ? (
                <tr>
                  <td
                    colSpan={userLevel >= ROLE_LEVEL.operator ? 8 : 7}
                    className="px-3 py-6 text-center text-gray-400"
                  >
                    No alerts found.
                  </td>
                </tr>
              ) : (
                alerts.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 border-b">
                      <SeverityBadge severity={a.severity} />
                    </td>
                    <td className="px-3 py-2 border-b font-mono text-xs" title={a.cluster_id}>
                      {truncateId(a.cluster_id)}
                    </td>
                    <td className="px-3 py-2 border-b font-mono text-xs">{a.metric}</td>
                    <td className="px-3 py-2 border-b">{a.message}</td>
                    <td className="px-3 py-2 border-b">{a.actual_value}</td>
                    <td className="px-3 py-2 border-b">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                          a.status === "active"
                            ? "bg-red-100 text-red-700"
                            : "bg-green-100 text-green-700"
                        }`}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 border-b text-gray-500">
                      {formatDate(a.last_triggered_at)}
                    </td>
                    {userLevel >= ROLE_LEVEL.operator && (
                      <td className="px-3 py-2 border-b">
                        {a.status === "active" && (
                          <button
                            onClick={() =>
                              resolveMut.mutate({ clusterId: a.cluster_id, alertId: a.id })
                            }
                            disabled={resolveMut.isPending}
                            className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                          >
                            Resolve
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
