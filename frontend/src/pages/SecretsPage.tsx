import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchSecrets, createSecret, deleteSecret } from "../api/secrets";
import type { Secret } from "../api/secrets";
import { useAuth } from "../hooks/useAuth";

const ROLE_LEVEL: Record<string, number> = { admin: 3, operator: 2, viewer: 1 };
const SECRET_TYPES = ["ssh_key", "admin_password", "keyfile", "s3_credential"];

export default function SecretsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userLevel = ROLE_LEVEL[user?.role ?? ""] ?? 0;

  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    type: SECRET_TYPES[0],
    plaintext: "",
  });

  const { data: secrets = [], isLoading, error } = useQuery<Secret[]>({
    queryKey: ["secrets"],
    queryFn: fetchSecrets,
  });

  const createMutation = useMutation({
    mutationFn: createSecret,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["secrets"] });
      setShowForm(false);
      setFormData({ name: "", type: SECRET_TYPES[0], plaintext: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSecret,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["secrets"] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createMutation.mutate({
      name: formData.name,
      type: formData.type,
      plaintext: formData.plaintext,
    });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Secrets</h1>
        {userLevel >= ROLE_LEVEL.operator && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
          >
            {showForm ? "Cancel" : "+ New Secret"}
          </button>
        )}
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white border rounded-lg p-4 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="my-ssh-key"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({ ...formData, type: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              {SECRET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
            <textarea
              required
              value={formData.plaintext}
              onChange={(e) => setFormData({ ...formData, plaintext: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm font-mono"
              rows={4}
              placeholder="Paste secret value here..."
            />
          </div>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating..." : "Create Secret"}
            </button>
            {createMutation.isError && (
              <span className="text-red-600 text-sm ml-3">
                {(createMutation.error as Error).message}
              </span>
            )}
          </div>
        </form>
      )}

      {isLoading && <p className="text-gray-500">Loading secrets...</p>}
      {error && <p className="text-red-600">Failed to load secrets: {(error as Error).message}</p>}

      {!isLoading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-4 py-2 border-b font-medium">Name</th>
                <th className="px-4 py-2 border-b font-medium">Type</th>
                <th className="px-4 py-2 border-b font-medium">Created</th>
                <th className="px-4 py-2 border-b font-medium">Created By</th>
                {userLevel >= ROLE_LEVEL.admin && (
                  <th className="px-4 py-2 border-b font-medium">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {secrets.length === 0 ? (
                <tr>
                  <td
                    colSpan={userLevel >= ROLE_LEVEL.admin ? 5 : 4}
                    className="px-4 py-6 text-center text-gray-400"
                  >
                    No secrets found.
                  </td>
                </tr>
              ) : (
                secrets.map((s: Secret) => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 border-b font-medium">{s.name}</td>
                    <td className="px-4 py-2 border-b">
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                        {s.type.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-2 border-b">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2 border-b">{s.created_by}</td>
                    {userLevel >= ROLE_LEVEL.admin && (
                      <td className="px-4 py-2 border-b">
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete secret "${s.name}"?`)) {
                              deleteMutation.mutate(s.id);
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
