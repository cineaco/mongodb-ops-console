const STATUS_CONFIG: Record<string, { color: string; icon: string }> = {
  pending:   { color: "bg-gray-100 text-gray-700",   icon: "\u23F3" },
  running:   { color: "bg-blue-100 text-blue-700",   icon: "\uD83D\uDD04" },
  success:   { color: "bg-green-100 text-green-700", icon: "\u2705" },
  failed:    { color: "bg-red-100 text-red-700",     icon: "\u274C" },
  cancelled: { color: "bg-gray-100 text-gray-600",   icon: "\u2298" },
};

export default function JobStatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${cfg.color}`}>
      <span>{cfg.icon}</span>
      {status}
    </span>
  );
}
