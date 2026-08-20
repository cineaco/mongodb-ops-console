import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  fetchLatestMetrics,
  fetchMetricsRange,
  refreshMetrics,
  type MetricPoint,
} from "../api/metrics";
import { useAuth } from "../hooks/useAuth";

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };

const RANGES = ["1h", "6h", "24h", "7d"] as const;
type Range = (typeof RANGES)[number];

interface ChartPoint {
  time: string;
  insert: number | null;
  query: number | null;
  update: number | null;
  del: number | null;
  connections_current: number | null;
  memory_resident_mb: number | null;
  fs_used_percent: number | null;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function transformPoints(points: MetricPoint[]): ChartPoint[] {
  return points.map((p) => ({
    time: formatTime(p.collected_at),
    insert: p.ops_per_second.insert,
    query: p.ops_per_second.query,
    update: p.ops_per_second.update,
    del: p.ops_per_second.delete,
    connections_current: p.connections_current,
    memory_resident_mb: p.memory_resident_mb,
    fs_used_percent: p.fs_used_percent,
  }));
}

function StatCard({
  title,
  value,
  sub,
  color,
}: {
  title: string;
  value: React.ReactNode;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="text-sm font-medium text-gray-500">{title}</div>
      <div className={`mt-1 text-2xl font-bold ${color ?? "text-gray-900"}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

function rsColor(state: string): string {
  if (state === "ok") return "text-green-600";
  if (state === "degraded") return "text-orange-500";
  return "text-red-600";
}

function rsBadgeBg(state: string): string {
  if (state === "ok") return "bg-green-100 text-green-800";
  if (state === "degraded") return "bg-orange-100 text-orange-800";
  return "bg-red-100 text-red-800";
}

export default function MonitoringTab({ clusterId }: { clusterId: string }) {
  const [range, setRange] = useState<Range>("1h");
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userLevel = ROLE_LEVEL[user?.role ?? ""] ?? 0;

  const latestQ = useQuery({
    queryKey: ["metrics-latest", clusterId],
    queryFn: () => fetchLatestMetrics(clusterId),
    refetchInterval: 30000,
  });

  const rangeQ = useQuery({
    queryKey: ["metrics-range", clusterId, range],
    queryFn: () => fetchMetricsRange(clusterId, range),
    refetchInterval: 30000,
  });

  const refreshMut = useMutation({
    mutationFn: () => refreshMetrics(clusterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["metrics-latest", clusterId] });
      queryClient.invalidateQueries({ queryKey: ["metrics-range", clusterId] });
    },
  });

  const latest = latestQ.data;
  const chartData = rangeQ.data ? transformPoints(rangeQ.data.points) : [];

  if (latestQ.isLoading || rangeQ.isLoading) {
    return <div className="py-12 text-center text-gray-500">Loading metrics...</div>;
  }

  if (!latest) {
    return <div className="py-12 text-center text-gray-400">No metrics available yet.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Controls row */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 rounded-lg border bg-white p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded px-3 py-1 text-sm font-medium transition ${
                range === r ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
        {userLevel >= ROLE_LEVEL.operator && (
          <button
            onClick={() => refreshMut.mutate()}
            disabled={refreshMut.isPending}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {refreshMut.isPending ? "Refreshing..." : "Refresh Now"}
          </button>
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="RS State"
          value={
            <span className={`inline-block rounded-full px-3 py-0.5 text-sm font-semibold ${rsBadgeBg(latest.rs_state)}`}>
              {latest.rs_state}
            </span>
          }
          sub={`${latest.members_up}/${latest.members_total} members up`}
          color={rsColor(latest.rs_state)}
        />
        <StatCard
          title="Replication Lag"
          value={latest.max_replication_lag_seconds != null ? `${latest.max_replication_lag_seconds}s` : "N/A"}
          sub="max lag across secondaries"
        />
        <StatCard
          title="Connections"
          value={latest.connections.current ?? "N/A"}
          sub={latest.connections.available != null ? `${latest.connections.available} available` : undefined}
        />
        <StatCard
          title="Disk Usage"
          value={latest.storage.fs_used_percent != null ? `${latest.storage.fs_used_percent.toFixed(1)}%` : "N/A"}
        />
      </div>

      {/* Charts */}
      {chartData.length === 0 ? (
        <div className="py-8 text-center text-gray-400">No time-series data available for this range.</div>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {/* Ops/sec */}
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-gray-600">Ops/sec</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="insert" stroke="#3b82f6" dot={false} name="insert" />
                <Line type="monotone" dataKey="query" stroke="#22c55e" dot={false} name="query" />
                <Line type="monotone" dataKey="update" stroke="#f59e0b" dot={false} name="update" />
                <Line type="monotone" dataKey="del" stroke="#ef4444" dot={false} name="delete" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Connections over time */}
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-gray-600">Connections</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="connections_current" stroke="#a855f7" dot={false} name="connections" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Memory (resident MB) */}
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-gray-600">Memory (Resident MB)</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="memory_resident_mb" stroke="#8b5cf6" dot={false} name="resident MB" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Disk Usage % */}
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-gray-600">Disk Usage %</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
                <Tooltip />
                <Line type="monotone" dataKey="fs_used_percent" stroke="#f97316" dot={false} name="disk %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
