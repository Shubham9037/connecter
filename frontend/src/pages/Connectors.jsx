import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, KeyRound, ShieldOff, RotateCcw, Plus, Check } from "lucide-react";
import { api } from "@/lib/api";
import CreateConnectorDialog from "@/components/CreateConnectorDialog";
import SecretRevealDialog from "@/components/SecretRevealDialog";

function formatDate(d) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleString();
  } catch {
    return String(d);
  }
}

function CopyChip({ value, testid }) {
  const [ok, setOk] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setOk(true);
    toast.success("Copied");
    setTimeout(() => setOk(false), 1200);
  };
  return (
    <button
      onClick={copy}
      data-testid={testid}
      className="inline-flex items-center gap-2 border border-gray-200 bg-white px-2 py-1 font-mono text-xs text-gray-800 hover:bg-gray-50"
    >
      {value}
      {ok ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3 text-gray-500" />}
    </button>
  );
}

function StatusBadge({ status }) {
  const color =
    status === "active"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : "border-red-200 bg-red-50 text-red-700";
  return (
    <span className={`inline-block border ${color} px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest`}>
      {status}
    </span>
  );
}

export default function Connectors() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openCreate, setOpenCreate] = useState(false);
  const [reveal, setReveal] = useState(null); // { connector, secret }

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await api.get("/connectors");
      setList(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load connectors");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleCreated = (data) => {
    setReveal(data);
    setOpenCreate(false);
    refresh();
  };

  const handleRegenerate = async (cid) => {
    if (!window.confirm("Regenerate secret? The previous secret stops working immediately.")) return;
    try {
      const r = await api.post(`/connectors/${cid}/regenerate`);
      setReveal(r.data);
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Regenerate failed");
    }
  };

  const handleRevoke = async (cid) => {
    const reason = window.prompt("Revoke this connector? Optional reason:");
    if (reason === null) return;
    try {
      await api.post(`/connectors/${cid}/revoke`, { reason });
      toast.success("Connector revoked");
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Revoke failed");
    }
  };

  return (
    <div data-testid="connectors-page">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-gray-500">
            Credentials
          </div>
          <h1 className="mt-1 font-heading text-4xl font-black tracking-tighter">
            Connectors
          </h1>
          <p className="mt-3 max-w-xl text-sm text-gray-600">
            Each connector holds one HMAC secret. Secrets are shown exactly
            once. Rotate anytime; revoke to disable a compromised endpoint.
          </p>
        </div>
        <button
          onClick={() => setOpenCreate(true)}
          data-testid="create-connector-btn"
          className="flex items-center gap-2 bg-[#002FA7] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#00227A]"
        >
          <Plus className="h-4 w-4" /> New connector
        </button>
      </div>

      <div className="border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left font-mono text-[10px] uppercase tracking-widest text-gray-500">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Connector ID</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Secret</th>
              <th className="px-4 py-3">Last Sync</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody data-testid="connectors-tbody">
            {loading && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-xs text-gray-500">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && list.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-sm text-gray-500" data-testid="connectors-empty">
                  No connectors yet. Create one to start signing sync requests.
                </td>
              </tr>
            )}
            {list.map((c) => (
              <tr key={c.connector_id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 font-semibold text-gray-900">{c.name}</td>
                <td className="px-4 py-3">
                  <CopyChip value={c.connector_id} testid={`copy-${c.connector_id}`} />
                </td>
                <td className="px-4 py-3 font-mono text-xs">{c.company_id}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={c.status} />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">••••{c.secret_last4}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{formatDate(c.last_sync_at)}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{formatDate(c.created_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {c.status === "active" && (
                      <>
                        <button
                          onClick={() => handleRegenerate(c.connector_id)}
                          data-testid={`regenerate-${c.connector_id}`}
                          className="flex items-center gap-1 border border-gray-200 px-2 py-1 text-xs font-semibold hover:bg-gray-100"
                        >
                          <RotateCcw className="h-3 w-3" /> Regenerate
                        </button>
                        <button
                          onClick={() => handleRevoke(c.connector_id)}
                          data-testid={`revoke-${c.connector_id}`}
                          className="flex items-center gap-1 border border-red-200 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
                        >
                          <ShieldOff className="h-3 w-3" /> Revoke
                        </button>
                      </>
                    )}
                    {c.status === "revoked" && (
                      <span className="font-mono text-[10px] uppercase tracking-widest text-gray-400">
                        <KeyRound className="mr-1 inline h-3 w-3" /> disabled
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {openCreate && (
        <CreateConnectorDialog
          onClose={() => setOpenCreate(false)}
          onCreated={handleCreated}
        />
      )}
      {reveal && <SecretRevealDialog data={reveal} onClose={() => setReveal(null)} />}
    </div>
  );
}
