import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchClusters, type Cluster } from "../api/clusters";
import client from "../api/client";
import MonitoringTab from "../components/MonitoringTab";
import AlertsTab from "../components/AlertsTab";
import OperationsTab from "../components/OperationsTab";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  healthy: "bg-green-100 text-green-800",
  degraded: "bg-orange-100 text-orange-800",
  failed: "bg-red-100 text-red-800",
};

const TABS = ["Overview", "Monitoring", "Alerts", "Operations"] as const;
type Tab = (typeof TABS)[number];

function InfoCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase text-gray-400">{label}</div>
      <div className="mt-1 text-sm font-semibold text-gray-900">{value}</div>
    </div>
  );
}

export default function ClusterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("Overview");

  const { data: clusters = [], isLoading } = useQuery<Cluster[]>({
    queryKey: ["clusters"],
    queryFn: fetchClusters,
  });

  const { data: hosts = [] } = useQuery<string[]>({
    queryKey: ["cluster-hosts", id],
    queryFn: async () => {
      const resp = await client.get<{ host: string }[]>(
        `/clusters/${id}/hosts`,
      );
      return resp.data.map((h) => h.host);
    },
    enabled: !!id && tab === "Operations",
  });

  const cluster = clusters.find((c) => c.id === id);

  if (isLoading) {
    return (
      <div className="py-12 text-center text-gray-500">Loading cluster...</div>
    );
  }

  if (!cluster) {
    return (
      <div className="py-12 text-center text-gray-400">
        Cluster not found.{" "}
        <Link to="/clusters" className="text-blue-600 hover:underline">
          Back to clusters
        </Link>
      </div>
    );
  }

  const statusColor =
    STATUS_COLORS[cluster.status] ?? "bg-gray-100 text-gray-800";

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500">
        <Link to="/clusters" className="hover:text-blue-600 hover:underline">
          Clusters
        </Link>
        <span className="mx-2">/</span>
        <span className="font-medium text-gray-900">{cluster.name}</span>
      </nav>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition ${
              tab === t
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "Overview" && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <InfoCard label="Topology" value={cluster.topology} />
          <InfoCard label="Version" value={cluster.mongodb_version} />
          <InfoCard label="Port" value={cluster.mongodb_port} />
          <InfoCard label="Replica Set" value={cluster.replicaset_name} />
          <InfoCard
            label="Status"
            value={
              <span
                className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${statusColor}`}
              >
                {cluster.status}
              </span>
            }
          />
          <InfoCard label="Description" value={cluster.description || "N/A"} />
        </div>
      )}

      {tab === "Monitoring" && id && <MonitoringTab clusterId={id} />}
      {tab === "Alerts" && id && <AlertsTab clusterId={id} />}
      {tab === "Operations" && id && (
        <OperationsTab clusterId={id} hosts={hosts} />
      )}
    </div>
  );
}
