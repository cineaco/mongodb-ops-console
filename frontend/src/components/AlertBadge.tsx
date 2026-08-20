import { useQuery } from "@tanstack/react-query";
import { fetchActiveAlertCount } from "../api/alerts";

export default function AlertBadge() {
  const { data: count } = useQuery({
    queryKey: ["active-alert-count"],
    queryFn: fetchActiveAlertCount,
    refetchInterval: 30000,
  });

  if (!count) return null;

  return (
    <span className="ml-2 inline-flex items-center justify-center rounded-full bg-red-600 px-1.5 py-0.5 text-xs font-bold leading-none text-white">
      {count > 99 ? "99+" : count}
    </span>
  );
}
