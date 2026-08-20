import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchUsers, createUser, deleteUser, updateUser } from "../api/users";
import type { User } from "../api/users";
import { useAuth } from "../hooks/useAuth";

const ROLES = ["admin", "operator", "viewer"];

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();

  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    username: "",
    password: "",
    email: "",
    role: "viewer",
  });

  const { data: users = [], isLoading, error } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setShowForm(false);
      setFormData({ username: "", password: "", email: "", role: "viewer" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, disabled }: { id: string; disabled: boolean }) =>
      updateUser(id, { disabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createMutation.mutate({
      username: formData.username,
      password: formData.password,
      role: formData.role,
      email: formData.email || undefined,
    });
  }

  const isAdmin = currentUser?.role === "admin";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Users</h1>
        {isAdmin && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
          >
            {showForm ? "Cancel" : "+ New User"}
          </button>
        )}
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white border rounded-lg p-4 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text"
              required
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="jdoe"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              required
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Strong password"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email (optional)</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="user@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating..." : "Create User"}
            </button>
            {createMutation.isError && (
              <span className="text-red-600 text-sm ml-3">
                {(createMutation.error as Error).message}
              </span>
            )}
          </div>
        </form>
      )}

      {isLoading && <p className="text-gray-500">Loading users...</p>}
      {error && <p className="text-red-600">Failed to load users: {(error as Error).message}</p>}

      {!isLoading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-4 py-2 border-b font-medium">Username</th>
                <th className="px-4 py-2 border-b font-medium">Email</th>
                <th className="px-4 py-2 border-b font-medium">Role</th>
                <th className="px-4 py-2 border-b font-medium">Status</th>
                <th className="px-4 py-2 border-b font-medium">Created</th>
                <th className="px-4 py-2 border-b font-medium">Last Login</th>
                {isAdmin && <th className="px-4 py-2 border-b font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td
                    colSpan={isAdmin ? 7 : 6}
                    className="px-4 py-6 text-center text-gray-400"
                  >
                    No users found.
                  </td>
                </tr>
              ) : (
                users.map((u: User) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 border-b font-medium">{u.username}</td>
                    <td className="px-4 py-2 border-b">{u.email ?? "-"}</td>
                    <td className="px-4 py-2 border-b">
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-2 border-b">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          u.disabled
                            ? "bg-red-100 text-red-800"
                            : "bg-green-100 text-green-800"
                        }`}
                      >
                        {u.disabled ? "Disabled" : "Active"}
                      </span>
                    </td>
                    <td className="px-4 py-2 border-b">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2 border-b">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleString()
                        : "-"}
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-2 border-b space-x-2">
                        {u.id !== currentUser?.id && (
                          <>
                            <button
                              onClick={() =>
                                toggleMutation.mutate({
                                  id: u.id,
                                  disabled: !u.disabled,
                                })
                              }
                              disabled={toggleMutation.isPending}
                              className="text-yellow-600 hover:text-yellow-800 text-sm disabled:opacity-50"
                            >
                              {u.disabled ? "Enable" : "Disable"}
                            </button>
                            <button
                              onClick={() => {
                                if (window.confirm(`Delete user "${u.username}"?`)) {
                                  deleteMutation.mutate(u.id);
                                }
                              }}
                              disabled={deleteMutation.isPending}
                              className="text-red-600 hover:text-red-800 text-sm disabled:opacity-50"
                            >
                              Delete
                            </button>
                          </>
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
