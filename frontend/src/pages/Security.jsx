import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertOctagon, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

const EVENT_LABELS = {
  invalid_signature: "Invalid signature",
  expired_timestamp: "Expired timestamp",
  future_timestamp: "Future timestamp",
  replay_attempt: "Replay attempt",
  missing_header: "Missing header",
  unknown_connector: "Unknown connector",
  revoked_connector: "Revoked connector used",
  company_mismatch: "Company mismatch",
  malformed_payload: "Malformed payload",
};

export default function Security() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [type, setType] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = { page: 1, page_size: 100 };
      if (type) params.event_type = type;
      const r = await api.get("/tally/security-events", { params });
      setItems(r.data.items);
      setTotal(r.data.total);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);

  return (
    <div data-testid="security-page">
      <div className="mb-6">
        <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-gray-500">Audit</div>
        <h1 className="mt-1 font-heading text-4xl font-black tracking-tighter">Security Events</h1>
        <p className="mt-3 max-w-2xl text-sm text-gray-600">
          Every rejected sync request is recorded here. Payloads, secrets and
          signatures are never stored — only the event type, request ID and
          minimal context.
        </p>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <label className="font-mono text-[10px] uppercase tracking-widest text-gray-500">
          Filter
        </label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          data-testid="security-filter"
          className="border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]"
        >
          <option value="">All events</option>
          {Object.entries(EVENT_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button
          onClick={fetchData}
          data-testid="refresh-security-btn"
          className="ml-auto flex items-center gap-2 border border-gray-200 px-3 py-1.5 text-xs font-semibold hover:bg-gray-100"
        >
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
      </div>

      <div className="border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left font-mono text-[10px] uppercase tracking-widest text-gray-500">
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Event</th>
              <th className="px-4 py-3">Connector</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">IP</th>
              <th className="px-4 py-3">Detail</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-xs text-gray-500">Loading…</td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500" data-testid="security-empty">
                  No security events. Your endpoint is quiet — that&apos;s a good thing.
                </td>
              </tr>
            )}
            {items.map((e) => (
              <tr key={e.request_id + e.created_at} className="border-b border-gray-100 hover:bg-gray-50" data-testid={`sec-event-${e.request_id}`}>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">
                  {new Date(e.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1 border border-red-200 bg-red-50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-red-700">
                    <AlertOctagon className="h-3 w-3" /> {EVENT_LABELS[e.event_type] || e.event_type}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{e.connector_id || "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{e.company_id || "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{e.ip || "—"}</td>
                <td className="px-4 py-3 text-xs text-gray-600">{e.detail || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 font-mono text-[10px] uppercase tracking-widest text-gray-500">
        {total} events total
      </div>
    </div>
  );
}
