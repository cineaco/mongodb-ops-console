import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  getJob,
  triggerRestartNode,
  triggerRollingRestart,
  triggerRotatePassword,
  triggerCreateUser,
  triggerDeleteUser,
  triggerPbmBackup,
  triggerPbmRestore,
  triggerPbmList,
  triggerMongodumpS3,
  triggerRerun,
  type JobCreated,
} from "../api/jobs";
import JobStatusBadge from "./JobStatusBadge";
import LogStream from "./LogStream";

interface Props {
  clusterId: string;
  operation: string;
  onClose: () => void;
  hosts?: string[];
}

export default function OperationModal({
  clusterId,
  operation,
  onClose,
  hosts = [],
}: Props) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [showLogStream, setShowLogStream] = useState(false);

  const set = (key: string, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  /* ── Poll job once submitted ── */
  const { data: job } = useQuery({
    queryKey: ["job", clusterId, jobId],
    queryFn: () => getJob(clusterId, jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "success" || status === "failed" || status === "cancelled")
        return false;
      return 2000;
    },
  });

  /* ── Submit mutation ── */
  const submit = useMutation<JobCreated, Error>({
    mutationFn: () => {
      switch (operation) {
        case "restart_node":
          return triggerRestartNode(clusterId, form.host ?? hosts[0] ?? "");
        case "rolling_restart":
          return triggerRollingRestart(clusterId);
        case "rotate_password":
          return triggerRotatePassword(clusterId, form.secret_id ?? "");
        case "create_app_user":
          return triggerCreateUser(clusterId, {
            database: form.database ?? "",
            username: form.username ?? "",
            password_secret_id: form.password_secret_id ?? "",
            roles: form.roles ?? "",
          });
        case "delete_app_user":
          return triggerDeleteUser(clusterId, {
            database: form.database ?? "",
            username: form.username ?? "",
          });
        case "pbm_backup":
          return triggerPbmBackup(clusterId);
        case "pbm_restore":
          return triggerPbmRestore(clusterId, form.timestamp ?? "");
        case "pbm_list":
          return triggerPbmList(clusterId);
        case "mongodump_s3":
          return triggerMongodumpS3(clusterId, {
            s3_bucket: form.s3_bucket ?? "",
            s3_prefix: form.s3_prefix ?? "",
            s3_region: form.s3_region ?? "",
            auth_method: form.auth_method ?? "credentials",
            s3_credential_secret_id: form.s3_credential_secret_id || undefined,
          });
        case "rerun":
          return triggerRerun(clusterId, selectedTags);
        default:
          return Promise.reject(new Error("Unknown operation"));
      }
    },
    onSuccess: (data) => {
      setJobId(data.job_id);
      if (operation === "rerun") {
        setShowLogStream(true);
      }
    },
  });

  /* ── Auto-submit for pbm_list ── */
  if (
    operation === "pbm_list" &&
    !jobId &&
    !submit.isPending &&
    !submit.isError
  ) {
    submit.mutate();
  }

  const TITLES: Record<string, string> = {
    restart_node: "Restart Node",
    rolling_restart: "Rolling Restart",
    rotate_password: "Rotate Password",
    create_app_user: "Create User",
    delete_app_user: "Delete User",
    pbm_backup: "PBM Backup",
    pbm_restore: "PBM Restore",
    pbm_list: "PBM List Backups",
    mongodump_s3: "Dump to S3",
    rerun: "Re-run Playbook",
  };

  const RERUN_TAGS = [
    "install",
    "config",
    "replication",
    "security",
    "backup",
    "monitoring",
    "summary",
    "validation",
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className={`w-full rounded-lg bg-white p-6 shadow-xl ${showLogStream ? "max-w-3xl" : "max-w-lg"}`}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold">
          {TITLES[operation] ?? operation}
        </h2>

        {/* ── LogStream for rerun ── */}
        {jobId && showLogStream ? (
          <div className="space-y-3">
            <LogStream jobId={jobId} />
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="rounded bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        ) : /* ── Polling state ── */
        jobId ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Status:</span>
              <JobStatusBadge status={job?.status ?? "pending"} />
            </div>
            {job?.error && (
              <div className="rounded bg-red-50 p-3 text-sm text-red-700">
                {job.error}
              </div>
            )}
            {job?.result && Object.keys(job.result).length > 0 && (
              <pre className="max-h-60 overflow-auto rounded bg-gray-50 p-3 text-xs">
                {JSON.stringify(job.result, null, 2)}
              </pre>
            )}
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="rounded bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          /* ── Form state ── */
          <div className="space-y-4">
            {operation === "restart_node" && (
              <label className="block">
                <span className="text-sm font-medium text-gray-700">Host</span>
                <select
                  value={form.host ?? hosts[0] ?? ""}
                  onChange={(e) => set("host", e.target.value)}
                  className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                >
                  {hosts.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {operation === "rolling_restart" && (
              <p className="text-sm text-gray-600">
                Are you sure you want to perform a rolling restart of all nodes?
              </p>
            )}

            {operation === "rotate_password" && (
              <label className="block">
                <span className="text-sm font-medium text-gray-700">
                  Secret ID
                </span>
                <input
                  type="text"
                  value={form.secret_id ?? ""}
                  onChange={(e) => set("secret_id", e.target.value)}
                  className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  placeholder="vault secret id for new password"
                />
              </label>
            )}

            {operation === "create_app_user" && (
              <>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Database
                  </span>
                  <input
                    type="text"
                    value={form.database ?? ""}
                    onChange={(e) => set("database", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Username
                  </span>
                  <input
                    type="text"
                    value={form.username ?? ""}
                    onChange={(e) => set("username", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Password Secret ID
                  </span>
                  <input
                    type="text"
                    value={form.password_secret_id ?? ""}
                    onChange={(e) => set("password_secret_id", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Roles (comma-separated)
                  </span>
                  <input
                    type="text"
                    value={form.roles ?? ""}
                    onChange={(e) => set("roles", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                    placeholder="readWrite,dbAdmin"
                  />
                </label>
              </>
            )}

            {operation === "delete_app_user" && (
              <>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Database
                  </span>
                  <input
                    type="text"
                    value={form.database ?? ""}
                    onChange={(e) => set("database", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Username
                  </span>
                  <input
                    type="text"
                    value={form.username ?? ""}
                    onChange={(e) => set("username", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
              </>
            )}

            {operation === "pbm_backup" && (
              <p className="text-sm text-gray-600">
                Are you sure you want to trigger a Percona backup?
              </p>
            )}

            {operation === "pbm_restore" && (
              <>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Backup Timestamp
                  </span>
                  <input
                    type="text"
                    value={form.timestamp ?? ""}
                    onChange={(e) => set("timestamp", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                    placeholder="2026-01-15T10:30:00Z"
                  />
                </label>
                <p className="text-xs text-orange-600">
                  Warning: Restore will overwrite current data. This action
                  cannot be undone.
                </p>
              </>
            )}

            {operation === "pbm_list" && (
              <p className="text-sm text-gray-500">Fetching backup list...</p>
            )}

            {operation === "mongodump_s3" && (
              <>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    S3 Bucket
                  </span>
                  <input
                    type="text"
                    value={form.s3_bucket ?? ""}
                    onChange={(e) => set("s3_bucket", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    S3 Prefix
                  </span>
                  <input
                    type="text"
                    value={form.s3_prefix ?? ""}
                    onChange={(e) => set("s3_prefix", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    S3 Region
                  </span>
                  <input
                    type="text"
                    value={form.s3_region ?? ""}
                    onChange={(e) => set("s3_region", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                    placeholder="us-east-1"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Auth Method
                  </span>
                  <select
                    value={form.auth_method ?? "credentials"}
                    onChange={(e) => set("auth_method", e.target.value)}
                    className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                  >
                    <option value="credentials">Credentials</option>
                    <option value="iam_role">IAM Role</option>
                  </select>
                </label>
                {(form.auth_method ?? "credentials") === "credentials" && (
                  <label className="block">
                    <span className="text-sm font-medium text-gray-700">
                      S3 Credential Secret ID
                    </span>
                    <input
                      type="text"
                      value={form.s3_credential_secret_id ?? ""}
                      onChange={(e) =>
                        set("s3_credential_secret_id", e.target.value)
                      }
                      className="mt-1 block w-full rounded border px-3 py-2 text-sm"
                    />
                  </label>
                )}
              </>
            )}

            {operation === "rerun" && (
              <div className="space-y-2">
                <p className="text-sm text-gray-600">
                  Select the tags to include in the re-run:
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {RERUN_TAGS.map((tag) => (
                    <label
                      key={tag}
                      className="flex items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={selectedTags.includes(tag)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedTags((prev) => [...prev, tag]);
                          } else {
                            setSelectedTags((prev) =>
                              prev.filter((t) => t !== tag),
                            );
                          }
                        }}
                      />
                      {tag}
                    </label>
                  ))}
                </div>
                {selectedTags.length === 0 && (
                  <p className="text-xs text-orange-600">
                    Select at least one tag to proceed.
                  </p>
                )}
              </div>
            )}

            {submit.isError && (
              <div className="rounded bg-red-50 p-3 text-sm text-red-700">
                {submit.error.message}
              </div>
            )}

            {operation !== "pbm_list" && (
              <div className="flex justify-end gap-2">
                <button
                  onClick={onClose}
                  className="rounded bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
                >
                  Cancel
                </button>
                <button
                  onClick={() => submit.mutate()}
                  disabled={
                    submit.isPending ||
                    (operation === "rerun" && selectedTags.length === 0)
                  }
                  className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {submit.isPending ? "Submitting..." : "Confirm"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
