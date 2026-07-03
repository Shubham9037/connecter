import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";
import { api } from "@/lib/api";

export default function CreateConnectorDialog({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !company.trim()) return;
    setBusy(true);
    try {
      const r = await api.post("/connectors", {
        name: name.trim(),
        company_id: company.trim(),
      });
      toast.success("Connector created");
      onCreated(r.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Create failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/40 backdrop-blur-sm"
      onClick={onClose}
      data-testid="create-connector-dialog"
    >
      <div
        className="w-full max-w-md border border-gray-200 bg-white"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-gray-500">
              New Credential
            </div>
            <h2 className="font-heading text-xl font-bold tracking-tight">
              Create connector
            </h2>
          </div>
          <button onClick={onClose} data-testid="dialog-close" className="text-gray-500 hover:text-gray-900">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={submit} className="space-y-5 px-6 py-6">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-gray-500">
              Connector name
            </label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Mumbai Branch – Windows PC"
              data-testid="connector-name-input"
              className="mt-2 w-full border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#002FA7]"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-gray-500">
              Company ID
            </label>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="ACME-01"
              data-testid="connector-company-input"
              className="mt-2 w-full border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#002FA7]"
            />
            <p className="mt-2 text-xs text-gray-500">
              Sync requests must carry this exact value in the{" "}
              <code className="border border-gray-200 bg-gray-50 px-1 py-0.5 font-mono text-[11px]">X-Company-ID</code>{" "}
              header.
            </p>
          </div>
          <div className="flex justify-end gap-3 border-t border-gray-200 pt-5">
            <button
              type="button"
              onClick={onClose}
              className="border border-gray-200 px-4 py-2 text-sm font-semibold hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              data-testid="submit-create-connector"
              className="bg-[#002FA7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#00227A] disabled:opacity-60"
            >
              {busy ? "Creating…" : "Create + reveal secret"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
