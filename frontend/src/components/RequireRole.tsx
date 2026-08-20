import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };

export default function RequireRole({ role, children }: { role: string; children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if ((ROLE_LEVEL[user.role] ?? 0) < ROLE_LEVEL[role]) {
    return <div className="p-8 text-red-600">Access denied. Requires {role} role or higher.</div>;
  }
  return <>{children}</>;
}
