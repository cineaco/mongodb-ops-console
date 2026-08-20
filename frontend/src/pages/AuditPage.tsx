import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAuditLogs } from "../api/audit";
import type { AuditLog } from "../api/audit";

const ACTIONS = [
  "all",
  "login",
  "login_failed",
  "logout",
  "create",
  "update",
  "delete",
];

export default function AuditPage() {
  const [actionFilter, setActionFilter] = useState("all");

  const { data: logs = [], isLoading, error } = useQuery<AuditLog[]>({
    queryKey: ["audit-logs", actionFilter],
    queryFn: () =>
      fetchAuditLogs({
        limit: 100,
        action: actionFilter === "all" ? undefined : actionFilter,
      }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Filter:</label>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          >
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a === "all" ? "All actions" : a.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && <p className="text-gray-500">Loading audit logs...</p>}
      {error && (
        <p className="text-red-600">Failed to load audit logs: {(error as Error).message}</p>
      )}

      {!isLoading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-4 py-2 border-b font-medium">Time</th>
                <th className="px-4 py-2 border-b font-medium">User</th>
                <th className="px-4 py-2 border-b font-medium">Action</th>
                <th className="px-4 py-2 border-b font-medium">Resource</th>
                <th className="px-4 py-2 border-b font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-400">
                    No audit logs found.
                  </td>
                </tr>
              ) : (
                logs.map((log: AuditLog) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 border-b whitespace-nowrap">
                      {new Date(log.occurred_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 border-b">{log.username ?? "-"}</td>
                    <td className="px-4 py-2 border-b">
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-2 border-b">
                      {log.resource_type ? (
                        <span>
                          {log.resource_type}
                          {log.resource_id && (
                            <span className="text-gray-400 ml-1" title={log.resource_id}>
                              /{log.resource_id.substring(0, 8)}
                            </span>
                          )}
                        </span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="px-4 py-2 border-b text-gray-500">
                      {log.ip_address ?? "-"}
                    </td>
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
