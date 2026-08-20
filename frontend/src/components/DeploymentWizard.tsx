import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createCluster } from "../api/clusters";
import { createSecret } from "../api/secrets";
import { triggerDeploy } from "../api/jobs";
import LogStream from "./LogStream";
import client from "../api/client";

/* ──────────────────────────────────────────────────────────────────────────────
 * Constants
 * ────────────────────────────────────────────────────────────────────────────── */

const TOPOLOGIES = [
  { value: "pss", label: "Primary-Secondary-Secondary (PSS)" },
  { value: "psa", label: "Primary-Secondary-Arbiter (PSA)" },
  { value: "psp", label: "Primary-Secondary-Percona (PSP)" },
  { value: "mixed_pss", label: "Mixed PSS (Percona Primary + Community)" },
  { value: "percona_pss", label: "Percona PSS" },
  { value: "percona_psa", label: "Percona PSA" },
  { value: "single_node", label: "Single Node Replica Set" },
  { value: "standalone", label: "Standalone (no replica set)" },
];

const VERSIONS = ["8.0", "7.0", "6.0", "5.0"];

const TOPOLOGY_HOSTS: Record<string, { role: string; label: string }[]> = {
  pss: [
    { role: "primary", label: "Primary" },
    { role: "secondary", label: "Secondary" },
    { role: "secondary2", label: "Secondary 2" },
  ],
  psa: [
    { role: "primary", label: "Primary" },
    { role: "secondary", label: "Secondary" },
    { role: "arbiter", label: "Arbiter" },
  ],
  psp: [
    { role: "primary", label: "Primary" },
    { role: "secondary", label: "Secondary" },
    { role: "percona", label: "Percona" },
  ],
  mixed_pss: [
    { role: "percona_primary", label: "Percona Primary" },
    { role: "secondary", label: "Secondary" },
    { role: "secondary2", label: "Secondary 2" },
  ],
  percona_pss: [
    { role: "percona_primary", label: "Percona Primary" },
    { role: "percona_secondary", label: "Percona Secondary" },
    { role: "percona_secondary2", label: "Percona Secondary 2" },
  ],
  percona_psa: [
    { role: "percona_primary", label: "Percona Primary" },
    { role: "percona_secondary", label: "Percona Secondary" },
    { role: "percona_arbiter", label: "Percona Arbiter" },
  ],
  single_node: [{ role: "primary", label: "Primary" }],
  standalone: [{ role: "primary", label: "Primary" }],
};

const DEPLOY_TAGS = ["install", "config", "replication", "security", "summary"];

const STEP_LABELS = ["Basics", "Hosts", "SSH Keys", "Admin", "Config", "Review", "Deploy"];

function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div className="mb-8 flex items-center justify-between">
      {STEP_LABELS.map((label, i) => {
        const num = i + 1;
        const active = num === currentStep;
        const done = num < currentStep;
        return (
          <div key={label} className="flex flex-1 flex-col items-center">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                active
                  ? "bg-blue-600 text-white"
                  : done
                    ? "bg-green-500 text-white"
                    : "bg-gray-200 text-gray-500"
              }`}
            >
              {done ? "\u2713" : num}
            </div>
            <span className="mt-1 text-xs text-gray-500">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────────
 * Types
 * ────────────────────────────────────────────────────────────────────────────── */

interface HostEntry {
  role: string;
  label: string;
  hostname: string;
  ip: string;
  ssh_user: string;
  ssh_port: number;
}

interface Basics {
  name: string;
  description: string;
  topology: string;
  mongodb_version: string;
  mongodb_port: number;
  replicaset_name: string;
}

interface SshKeys {
  sameForAll: boolean;
  keys: Record<string, string>; // role -> key content
}

interface AdminCreds {
  admin_username: string;
  admin_password: string;
}

interface Config {
  enable_external_volume: boolean;
  enable_monitoring: boolean;
  backup_enabled: boolean;
  create_admin_user: boolean;
  slack_enabled: boolean;
}

/* ──────────────────────────────────────────────────────────────────────────────
 * Component
 * ────────────────────────────────────────────────────────────────────────────── */

export default function DeploymentWizard() {
  const navigate = useNavigate();

  /* Step state */
  const [step, setStep] = useState(1);
  const [basics, setBasics] = useState<Basics>({
    name: "",
    description: "",
    topology: "pss",
    mongodb_version: "7.0",
    mongodb_port: 37017,
    replicaset_name: "rs0",
  });
  const [hosts, setHosts] = useState<HostEntry[]>(
    TOPOLOGY_HOSTS["pss"].map((h) => ({
      ...h,
      hostname: h.role,
      ip: "",
      ssh_user: "ubuntu",
      ssh_port: 22,
    })),
  );
  const [sshKeys, setSshKeys] = useState<SshKeys>({ sameForAll: true, keys: {} });
  const [adminCreds, setAdminCreds] = useState<AdminCreds>({
    admin_username: "admin",
    admin_password: "",
  });
  const [config, setConfig] = useState<Config>({
    enable_external_volume: true,
    enable_monitoring: false,
    backup_enabled: false,
    create_admin_user: true,
    slack_enabled: false,
  });

  /* Deploy state */
  const [deploying, setDeploying] = useState(false);
  const [deployJobId, setDeployJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const TOTAL_STEPS = 7;

  /* ── Topology change handler ── */
  function handleTopologyChange(topo: string) {
    setBasics((b) => ({ ...b, topology: topo }));
    const newHosts = (TOPOLOGY_HOSTS[topo] ?? []).map((h) => ({
      ...h,
      hostname: h.role,
      ip: "",
      ssh_user: "ubuntu",
      ssh_port: 22,
    }));
    setHosts(newHosts);
    setSshKeys({ sameForAll: true, keys: {} });
  }

  /* ── Host field updater ── */
  function updateHost(idx: number, field: keyof HostEntry, value: string | number) {
    setHosts((prev) => prev.map((h, i) => (i === idx ? { ...h, [field]: value } : h)));
  }

  /* ── Submit logic ── */
  async function handleSubmit(andDeploy: boolean) {
    setDeploying(true);
    setError(null);
    try {
      /* 1. Create SSH key secrets */
      const sshSecretIds: Record<string, string> = {};
      if (sshKeys.sameForAll) {
        const keyContent = sshKeys.keys[hosts[0]?.role] ?? sshKeys.keys["_all"] ?? "";
        if (keyContent) {
          const secret = await createSecret({
            name: `${basics.name}-ssh-key`,
            type: "ssh_key",
            plaintext: keyContent,
          });
          for (const h of hosts) {
            sshSecretIds[h.role] = secret.id;
          }
        }
      } else {
        for (const h of hosts) {
          const keyContent = sshKeys.keys[h.role] ?? "";
          if (keyContent) {
            const secret = await createSecret({
              name: `${basics.name}-ssh-${h.role}`,
              type: "ssh_key",
              plaintext: keyContent,
            });
            sshSecretIds[h.role] = secret.id;
          }
        }
      }

      /* 2. Create admin password secret */
      let adminSecretId: string | undefined;
      if (adminCreds.admin_password) {
        const secret = await createSecret({
          name: `${basics.name}-admin-password`,
          type: "password",
          plaintext: adminCreds.admin_password,
        });
        adminSecretId = secret.id;
      }

      /* 3. Create cluster */
      const cluster = await createCluster({
        name: basics.name,
        topology: basics.topology,
        mongodb_version: basics.mongodb_version,
        mongodb_port: basics.mongodb_port,
        replicaset_name: basics.replicaset_name,
        description: basics.description || undefined,
        config: {
          ...config,
          admin_username: adminCreds.admin_username,
          admin_credentials_secret_id: adminSecretId,
        },
      });

      /* 4. Create hosts */
      for (const h of hosts) {
        await client.post(`/clusters/${cluster.id}/hosts`, {
          hostname: h.hostname,
          ip_address: h.ip,
          role: h.role,
          ssh_user: h.ssh_user,
          ssh_port: h.ssh_port,
          ssh_key_secret_id: sshSecretIds[h.role] ?? "",
        });
      }

      /* 5. Deploy if requested */
      if (andDeploy) {
        const job = await triggerDeploy(cluster.id, DEPLOY_TAGS);
        setDeployJobId(job.job_id);
      } else {
        navigate(`/clusters/${cluster.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setDeploying(false);
    }
  }



  /* ──────────────────────────────────────────────────────────────────────────
   * If deploy is streaming, show LogStream
   * ────────────────────────────────────────────────────────────────────────── */
  if (deployJobId) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Deployment in Progress</h2>
        <LogStream
          jobId={deployJobId}
          onComplete={(success) => {
            if (success) {
              /* Optionally navigate after success */
            }
          }}
        />
      </div>
    );
  }

  /* ──────────────────────────────────────────────────────────────────────────
   * Step renderers
   * ────────────────────────────────────────────────────────────────────────── */

  function renderStep1() {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cluster Name *</label>
          <input
            type="text"
            required
            value={basics.name}
            onChange={(e) => setBasics({ ...basics, name: e.target.value })}
            className="w-full rounded border px-3 py-2 text-sm"
            placeholder="my-cluster"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <input
            type="text"
            value={basics.description}
            onChange={(e) => setBasics({ ...basics, description: e.target.value })}
            className="w-full rounded border px-3 py-2 text-sm"
            placeholder="Optional description"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Topology</label>
          <select
            value={basics.topology}
            onChange={(e) => handleTopologyChange(e.target.value)}
            className="w-full rounded border px-3 py-2 text-sm"
          >
            {TOPOLOGIES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">MongoDB Version</label>
          <select
            value={basics.mongodb_version}
            onChange={(e) => setBasics({ ...basics, mongodb_version: e.target.value })}
            className="w-full rounded border px-3 py-2 text-sm"
          >
            {VERSIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
          <input
            type="number"
            value={basics.mongodb_port}
            onChange={(e) =>
              setBasics({ ...basics, mongodb_port: parseInt(e.target.value, 10) || 37017 })
            }
            className="w-full rounded border px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Replica Set Name</label>
          <input
            type="text"
            value={basics.replicaset_name}
            onChange={(e) => setBasics({ ...basics, replicaset_name: e.target.value })}
            className="w-full rounded border px-3 py-2 text-sm"
          />
        </div>
      </div>
    );
  }

  function renderStep2() {
    return (
      <div className="space-y-4">
        <p className="text-sm text-gray-500">
          Configure each host for your <strong>{basics.topology}</strong> topology.
        </p>
        {hosts.map((h, idx) => (
          <div key={h.role} className="rounded border bg-gray-50 p-4">
            <h4 className="mb-3 font-medium text-gray-800">{h.label}</h4>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className="block text-xs font-medium text-gray-600">Hostname</label>
                <input
                  type="text"
                  value={h.hostname}
                  onChange={(e) => updateHost(idx, "hostname", e.target.value)}
                  className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600">IP Address *</label>
                <input
                  type="text"
                  value={h.ip}
                  onChange={(e) => updateHost(idx, "ip", e.target.value)}
                  className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                  placeholder="10.0.1.10"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600">SSH User</label>
                <input
                  type="text"
                  value={h.ssh_user}
                  onChange={(e) => updateHost(idx, "ssh_user", e.target.value)}
                  className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600">SSH Port</label>
                <input
                  type="number"
                  value={h.ssh_port}
                  onChange={(e) =>
                    updateHost(idx, "ssh_port", parseInt(e.target.value, 10) || 22)
                  }
                  className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderStep3() {
    const firstRole = hosts[0]?.role ?? "_all";
    return (
      <div className="space-y-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={sshKeys.sameForAll}
            onChange={(e) => setSshKeys({ ...sshKeys, sameForAll: e.target.checked })}
          />
          Use same SSH key for all hosts
        </label>

        {sshKeys.sameForAll ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              SSH Private Key (all hosts)
            </label>
            <textarea
              rows={6}
              value={sshKeys.keys[firstRole] ?? ""}
              onChange={(e) =>
                setSshKeys({ ...sshKeys, keys: { [firstRole]: e.target.value } })
              }
              className="w-full rounded border px-3 py-2 font-mono text-xs"
              placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
            />
          </div>
        ) : (
          hosts.map((h) => (
            <div key={h.role}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                SSH Key for {h.label} ({h.hostname})
              </label>
              <textarea
                rows={4}
                value={sshKeys.keys[h.role] ?? ""}
                onChange={(e) =>
                  setSshKeys({
                    ...sshKeys,
                    keys: { ...sshKeys.keys, [h.role]: e.target.value },
                  })
                }
                className="w-full rounded border px-3 py-2 font-mono text-xs"
                placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
              />
            </div>
          ))
        )}
      </div>
    );
  }

  function renderStep4() {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Admin Username</label>
          <input
            type="text"
            value={adminCreds.admin_username}
            onChange={(e) =>
              setAdminCreds({ ...adminCreds, admin_username: e.target.value })
            }
            className="w-full rounded border px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Admin Password</label>
          <input
            type="password"
            value={adminCreds.admin_password}
            onChange={(e) =>
              setAdminCreds({ ...adminCreds, admin_password: e.target.value })
            }
            className="w-full rounded border px-3 py-2 text-sm"
            placeholder="Strong password"
          />
        </div>
      </div>
    );
  }

  function renderStep5() {
    const toggles: { key: keyof Config; label: string; desc: string }[] = [
      {
        key: "enable_external_volume",
        label: "External Volume",
        desc: "Mount and format an external EBS/data volume",
      },
      {
        key: "enable_monitoring",
        label: "Monitoring",
        desc: "Deploy mongodb_exporter + node_exporter",
      },
      {
        key: "backup_enabled",
        label: "Percona Backup",
        desc: "Install and configure PBM",
      },
      {
        key: "create_admin_user",
        label: "Create Admin User",
        desc: "Create the MongoDB admin user during deployment",
      },
      {
        key: "slack_enabled",
        label: "Slack Notifications",
        desc: "Send Slack notification on completion",
      },
    ];

    return (
      <div className="space-y-3">
        {toggles.map((t) => (
          <label
            key={t.key}
            className="flex items-start gap-3 rounded border bg-white p-3 cursor-pointer hover:border-blue-300"
          >
            <input
              type="checkbox"
              checked={config[t.key]}
              onChange={(e) => setConfig({ ...config, [t.key]: e.target.checked })}
              className="mt-0.5"
            />
            <div>
              <div className="text-sm font-medium text-gray-800">{t.label}</div>
              <div className="text-xs text-gray-500">{t.desc}</div>
            </div>
          </label>
        ))}
      </div>
    );
  }

  function renderStep6() {
    return (
      <div className="space-y-4 text-sm">
        <div className="rounded border bg-gray-50 p-4">
          <h4 className="mb-2 font-semibold text-gray-700">Basics</h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
            <dt className="text-gray-500">Name</dt>
            <dd>{basics.name}</dd>
            <dt className="text-gray-500">Topology</dt>
            <dd>{basics.topology}</dd>
            <dt className="text-gray-500">Version</dt>
            <dd>{basics.mongodb_version}</dd>
            <dt className="text-gray-500">Port</dt>
            <dd>{basics.mongodb_port}</dd>
            <dt className="text-gray-500">Replica Set</dt>
            <dd>{basics.replicaset_name}</dd>
            {basics.description && (
              <>
                <dt className="text-gray-500">Description</dt>
                <dd>{basics.description}</dd>
              </>
            )}
          </dl>
        </div>

        <div className="rounded border bg-gray-50 p-4">
          <h4 className="mb-2 font-semibold text-gray-700">Hosts</h4>
          <div className="space-y-1">
            {hosts.map((h) => (
              <div key={h.role} className="flex gap-2">
                <span className="font-medium text-gray-600">{h.label}:</span>
                <span>
                  {h.hostname} ({h.ip}) - {h.ssh_user}:{h.ssh_port}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded border bg-gray-50 p-4">
          <h4 className="mb-2 font-semibold text-gray-700">SSH Keys</h4>
          <p className="text-gray-500">
            {sshKeys.sameForAll
              ? "Same key for all hosts"
              : `${Object.keys(sshKeys.keys).length} individual key(s)`}
          </p>
        </div>

        <div className="rounded border bg-gray-50 p-4">
          <h4 className="mb-2 font-semibold text-gray-700">Admin Credentials</h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
            <dt className="text-gray-500">Username</dt>
            <dd>{adminCreds.admin_username}</dd>
            <dt className="text-gray-500">Password</dt>
            <dd>{"*".repeat(adminCreds.admin_password.length || 0)}</dd>
          </dl>
        </div>

        <div className="rounded border bg-gray-50 p-4">
          <h4 className="mb-2 font-semibold text-gray-700">Configuration</h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
            <dt className="text-gray-500">External Volume</dt>
            <dd>{config.enable_external_volume ? "Yes" : "No"}</dd>
            <dt className="text-gray-500">Monitoring</dt>
            <dd>{config.enable_monitoring ? "Yes" : "No"}</dd>
            <dt className="text-gray-500">Backup</dt>
            <dd>{config.backup_enabled ? "Yes" : "No"}</dd>
            <dt className="text-gray-500">Create Admin</dt>
            <dd>{config.create_admin_user ? "Yes" : "No"}</dd>
            <dt className="text-gray-500">Slack</dt>
            <dd>{config.slack_enabled ? "Yes" : "No"}</dd>
          </dl>
        </div>
      </div>
    );
  }

  function renderStep7() {
    return (
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Choose how to proceed with your cluster configuration.
        </p>

        {error && (
          <div className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => handleSubmit(true)}
            disabled={deploying}
            className="rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {deploying ? "Creating..." : "Create & Deploy"}
          </button>
          <button
            onClick={() => handleSubmit(false)}
            disabled={deploying}
            className="rounded bg-gray-600 px-6 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
          >
            {deploying ? "Creating..." : "Create Only"}
          </button>
        </div>
      </div>
    );
  }

  const stepRenderers = [renderStep1, renderStep2, renderStep3, renderStep4, renderStep5, renderStep6, renderStep7];

  /* ──────────────────────────────────────────────────────────────────────────
   * Main render
   * ────────────────────────────────────────────────────────────────────────── */
  return (
    <div className="mx-auto max-w-4xl">
      <StepIndicator currentStep={step} />

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">
          Step {step}: {STEP_LABELS[step - 1]}
        </h2>

        {stepRenderers[step - 1]()}
      </div>

      {/* Navigation buttons */}
      {step < TOTAL_STEPS && (
        <div className="mt-4 flex justify-between">
          <button
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1}
            className="rounded border bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-30"
          >
            Previous
          </button>
          <button
            onClick={() => setStep((s) => Math.min(TOTAL_STEPS, s + 1))}
            disabled={step === TOTAL_STEPS}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
      {step === TOTAL_STEPS && (
        <div className="mt-4">
          <button
            onClick={() => setStep((s) => s - 1)}
            className="rounded border bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Previous
          </button>
        </div>
      )}
    </div>
  );
}
