import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const CARDS = [
  { key: "connectors_active", label: "Active Connectors", accent: "text-gray-900" },
  { key: "syncs_24h", label: "Syncs · 24h", accent: "text-gray-900" },
  { key: "successes_24h", label: "Successful · 24h", accent: "text-[#059669]" },
  { key: "security_events_24h", label: "Security Events · 24h", accent: "text-[#D97706]" },
];

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.get("/tally/stats")
      .then((r) => setStats(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Failed to load stats"));
  }, []);

  return (
    <div data-testid="overview-page">
      <div className="mb-8">
        <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-gray-500">
          Dashboard
        </div>
        <h1 className="mt-1 font-heading text-4xl font-black tracking-tighter">
          Overview
        </h1>
        <p className="mt-3 max-w-xl text-sm text-gray-600">
          Health snapshot for the last 24 hours. Numbers are computed live
          against the audit log and never cached.
        </p>
      </div>

      {err && (
        <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700" data-testid="overview-error">
          {err}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {CARDS.map((c) => (
          <div
            key={c.key}
            data-testid={`stat-${c.key}`}
            className="border border-gray-200 bg-white p-6"
          >
            <div className="font-mono text-[10px] uppercase tracking-widest text-gray-500">
              {c.label}
            </div>
            <div className={`mt-3 font-heading text-4xl font-black tracking-tighter ${c.accent}`}>
              {stats ? stats[c.key] ?? 0 : "—"}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="border border-gray-200 p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest text-gray-500">
            Replay Attempts · 24h
          </div>
          <div className="mt-3 font-heading text-3xl font-black tracking-tighter text-gray-900">
            {stats ? stats.replay_attempts_24h ?? 0 : "—"}
          </div>
          <p className="mt-3 text-xs text-gray-500">
            Requests rejected by the nonce store. A non-zero value here means an
            attacker (or a mis-configured connector) is retrying signed requests.
          </p>
        </div>
        <div className="border border-gray-200 p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest text-gray-500">
            Connectors Total
          </div>
          <div className="mt-3 font-heading text-3xl font-black tracking-tighter text-gray-900">
            {stats ? stats.connectors_total ?? 0 : "—"}
          </div>
          <p className="mt-3 text-xs text-gray-500">
            Includes revoked connectors. Revoked credentials remain in the
            table for audit purposes but cannot authenticate.
          </p>
        </div>
      </div>
    </div>
  );
}
