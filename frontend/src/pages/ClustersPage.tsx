import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchClusters, deleteCluster } from "../api/clusters";
import type { Cluster } from "../api/clusters";
import { useAuth } from "../hooks/useAuth";

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  healthy: "bg-green-100 text-green-800",
  degraded: "bg-orange-100 text-orange-800",
  failed: "bg-red-100 text-red-800",
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${color}`}
    >
      {status}
    </span>
  );
}

export default function ClustersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userLevel = ROLE_LEVEL[user?.role ?? ""] ?? 0;

  const {
    data: clusters = [],
    isLoading,
    error,
  } = useQuery<Cluster[]>({
    queryKey: ["clusters"],
    queryFn: fetchClusters,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCluster,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Clusters</h1>
        {userLevel >= ROLE_LEVEL.operator && (
          <Link
            to="/clusters/new"
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
          >
            + New Cluster
          </Link>
        )}
      </div>

      {isLoading && <p className="text-gray-500">Loading clusters...</p>}
      {error && (
        <p className="text-red-600">
          Failed to load clusters: {(error as Error).message}
        </p>
      )}

      {!isLoading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-4 py-2 border-b font-medium">Name</th>
                <th className="px-4 py-2 border-b font-medium">Topology</th>
                <th className="px-4 py-2 border-b font-medium">Version</th>
                <th className="px-4 py-2 border-b font-medium">Port</th>
                <th className="px-4 py-2 border-b font-medium">Status</th>
                {userLevel >= ROLE_LEVEL.admin && (
                  <th className="px-4 py-2 border-b font-medium">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {clusters.length === 0 ? (
                <tr>
                  <td
                    colSpan={userLevel >= ROLE_LEVEL.admin ? 6 : 5}
                    className="px-4 py-6 text-center text-gray-400"
                  >
                    No clusters found.
                  </td>
                </tr>
              ) : (
                clusters.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 border-b font-medium">
                      <Link
                        to={`/clusters/${c.id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 border-b">{c.topology}</td>
                    <td className="px-4 py-2 border-b">{c.mongodb_version}</td>
                    <td className="px-4 py-2 border-b">{c.mongodb_port}</td>
                    <td className="px-4 py-2 border-b">
                      <StatusBadge status={c.status} />
                    </td>
                    {userLevel >= ROLE_LEVEL.admin && (
                      <td className="px-4 py-2 border-b">
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete cluster "${c.name}"?`)) {
                              deleteMutation.mutate(c.id);
                            }
                          }}
                          disabled={deleteMutation.isPending}
                          className="text-red-600 hover:text-red-800 text-sm disabled:opacity-50"
                        >
                          Delete
                        </button>
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
