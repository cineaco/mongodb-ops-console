import { useState } from "react";
import client from "../api/client";
import { useAuth } from "../hooks/useAuth";

export default function AccountPage() {
  const { user } = useAuth();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(
    null,
  );
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus(null);

    if (password.length < 8) {
      setStatus({ type: "error", message: "Password must be at least 8 characters." });
      return;
    }

    if (password !== confirmPassword) {
      setStatus({ type: "error", message: "Passwords do not match." });
      return;
    }

    setLoading(true);
    try {
      await client.patch(`/users/${user?.id}`, { password });
      setPassword("");
      setConfirmPassword("");
      setStatus({ type: "success", message: "Password changed successfully." });
    } catch (err) {
      setStatus({
        type: "error",
        message: (err as Error).message || "Failed to change password.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Account</h1>

      <div className="bg-white border rounded-lg p-6 max-w-md">
        <div className="mb-4">
          <p className="text-sm text-gray-500">Username</p>
          <p className="font-medium">{user?.username}</p>
        </div>
        <div className="mb-4">
          <p className="text-sm text-gray-500">Role</p>
          <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
            {user?.role}
          </span>
        </div>
        <div className="mb-6">
          <p className="text-sm text-gray-500">Email</p>
          <p className="font-medium">{user?.email ?? "-"}</p>
        </div>

        <hr className="mb-4" />
        <h2 className="text-lg font-semibold mb-4">Change Password</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Min 8 characters"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Repeat password"
            />
          </div>
          <div>
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm disabled:opacity-50"
            >
              {loading ? "Saving..." : "Change Password"}
            </button>
          </div>
          {status && (
            <p
              className={`text-sm ${
                status.type === "success" ? "text-green-600" : "text-red-600"
              }`}
            >
              {status.message}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
