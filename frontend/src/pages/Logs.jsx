import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

const STATUS_OPTIONS = ["", "success", "failed", "duplicate"];

function StatusPill({ s }) {
  const color =
    s === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : s === "duplicate"
        ? "border-blue-200 bg-blue-50 text-blue-700"
        : s === "failed"
          ? "border-red-200 bg-red-50 text-red-700"
          : "border-gray-200 bg-gray-50 text-gray-700";
  return (
    <span className={`inline-block border ${color} px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest`}>
      {s}
    </span>
  );
}

function Row({ item }) {
  const [open, setOpen] = useState(false);
  const dt = item.created_at ? new Date(item.created_at).toLocaleString() : "—";
  return (
    <>
      <tr
        className="cursor-pointer border-b border-gray-100 hover:bg-gray-50"
        onClick={() => setOpen(!open)}
        data-testid={`log-row-${item.request_id}`}
      >
        <td className="px-4 py-3">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </td>
        <td className="px-4 py-3 font-mono text-xs text-gray-500">{dt}</td>
        <td className="px-4 py-3 font-mono text-xs">{item.connector_id}</td>
        <td className="px-4 py-3 font-mono text-xs">{item.company_id}</td>
        <td className="px-4 py-3 font-mono text-xs">{item.entity_type || "—"}</td>
        <td className="px-4 py-3 text-right font-mono text-xs">{item.record_count}</td>
        <td className="px-4 py-3">
          <StatusPill s={item.status} />
        </td>
        <td className="px-4 py-3 text-right font-mono text-xs">{item.duration_ms}ms</td>
      </tr>
      {open && (
        <tr className="border-b border-gray-100 bg-gray-50">
          <td colSpan={8} className="px-4 py-4">
            <pre
              className="max-h-64 overflow-auto border border-gray-200 bg-white p-3 font-mono text-[11px] text-gray-800"
              data-testid={`log-detail-${item.request_id}`}
            >
{JSON.stringify(item, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

export default function Logs() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [filters, setFilters] = useState({ connector_id: "", company_id: "", status: "" });
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (filters.connector_id) params.connector_id = filters.connector_id;
      if (filters.company_id) params.company_id = filters.company_id;
      if (filters.status) params.status = filters.status;
      const r = await api.get("/tally/logs", { params });
      setItems(r.data.items);
      setTotal(r.data.total);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const applyFilters = (e) => {
    e.preventDefault();
    setPage(1);
    fetchData();
  };

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div data-testid="logs-page">
      <div className="mb-6">
        <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-gray-500">Audit</div>
        <h1 className="mt-1 font-heading text-4xl font-black tracking-tighter">Sync Logs</h1>
      </div>

      <form onSubmit={applyFilters} className="mb-4 flex flex-wrap items-end gap-3 border border-gray-200 bg-white p-4">
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest text-gray-500">
            Connector ID
          </label>
          <input
            value={filters.connector_id}
            onChange={(e) => setFilters((f) => ({ ...f, connector_id: e.target.value }))}
            data-testid="filter-connector"
            className="mt-1 border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]"
          />
        </div>
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest text-gray-500">
            Company ID
          </label>
          <input
            value={filters.company_id}
            onChange={(e) => setFilters((f) => ({ ...f, company_id: e.target.value }))}
            data-testid="filter-company"
            className="mt-1 border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]"
          />
        </div>
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest text-gray-500">Status</label>
          <select
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            data-testid="filter-status"
            className="mt-1 border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s || "any"}</option>
            ))}
          </select>
        </div>
        <div className="flex-1" />
        <button
          type="submit"
          data-testid="apply-filters-btn"
          className="flex items-center gap-2 bg-[#002FA7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#00227A]"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </form>

      <div className="border border-gray-200 bg-white">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left font-mono text-[10px] uppercase tracking-widest text-gray-500">
              <th className="w-8 px-4 py-3" />
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Connector</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Entity</th>
              <th className="px-4 py-3 text-right">Rows</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Duration</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-xs text-gray-500">Loading…</td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-sm text-gray-500" data-testid="logs-empty">
                  No sync activity yet.
                </td>
              </tr>
            )}
            {items.map((it) => (
              <Row key={it.request_id + it.created_at} item={it} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-xs">
        <span className="font-mono text-gray-500">
          {total} entries · page {page} of {pages}
        </span>
        <div className="flex gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            data-testid="prev-page-btn"
            className="border border-gray-200 px-3 py-1 font-semibold hover:bg-gray-100 disabled:opacity-40"
          >
            ← Prev
          </button>
          <button
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
            data-testid="next-page-btn"
            className="border border-gray-200 px-3 py-1 font-semibold hover:bg-gray-100 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
