import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { logout } from "../api/auth";
import AlertBadge from "./AlertBadge";

const NAV_ITEMS = [
  { to: "/clusters", label: "Clusters", minRole: "viewer" },
  { to: "/users", label: "Users", minRole: "admin" },
  { to: "/secrets", label: "Secrets", minRole: "operator" },
  { to: "/alerts", label: "Alerts", minRole: "viewer" },
  { to: "/audit", label: "Audit Log", minRole: "viewer" },
];

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };

export default function Layout() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const userLevel = ROLE_LEVEL[user?.role ?? ""] ?? 0;

  async function handleLogout() {
    await logout();
    setUser(null);
    navigate("/login");
  }

  return (
    <div className="flex h-screen bg-gray-100">
      <aside className="flex w-56 flex-col bg-gray-900 text-white">
        <div className="p-4 text-lg font-bold">MongoDB Dashboard</div>
        <nav className="flex-1 space-y-1 px-2">
          {NAV_ITEMS.filter(
            (item) => userLevel >= ROLE_LEVEL[item.minRole],
          ).map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="block rounded px-3 py-2 text-sm hover:bg-gray-700"
            >
              {item.label}
              {item.to === "/alerts" && <AlertBadge />}
            </Link>
          ))}
        </nav>
        <div className="border-t border-gray-700 p-4">
          <div className="text-sm text-gray-400">
            {user?.username} ({user?.role})
          </div>
          <div className="mt-2 flex gap-2">
            <Link
              to="/account"
              className="text-xs text-blue-400 hover:underline"
            >
              Account
            </Link>
            <button
              onClick={handleLogout}
              className="text-xs text-red-400 hover:underline"
            >
              Logout
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
