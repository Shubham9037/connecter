import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Copy, Check } from "lucide-react";

export default function SecretRevealDialog({ data, onClose }) {
  const [confirmed, setConfirmed] = useState(false);
  const [copied, setCopied] = useState(false);
  const { connector, secret } = data;

  const copy = async () => {
    await navigator.clipboard.writeText(secret);
    setCopied(true);
    toast.success("Secret copied to clipboard");
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/40 backdrop-blur-sm"
      data-testid="secret-reveal-dialog"
    >
      <div className="w-full max-w-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#D97706]">
            One-time reveal
          </div>
          <h2 className="font-heading text-xl font-bold tracking-tight">
            Save this secret now
          </h2>
        </div>

        <div className="px-6 py-6">
          <div className="mb-4 flex items-start gap-3 border-l-4 border-[#D97706] bg-[#FEF3C7] p-4">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-[#D97706]" />
            <div className="text-xs text-[#78350F]">
              This is the <b>only time</b> Razio will show this secret. If you
              lose it, you must regenerate — the old value will be rejected on
              first use.
            </div>
          </div>

          <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-gray-500">
            Connector
          </div>
          <div className="mb-4 font-mono text-sm text-gray-800">
            {connector.connector_id} <span className="text-gray-400">— {connector.name}</span>
          </div>

          <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-gray-500">
            HMAC Secret
          </div>
          <div className="flex items-center gap-2">
            <div
              data-testid="revealed-secret"
              className="flex-1 break-all border border-gray-300 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-900"
            >
              {secret}
            </div>
            <button
              onClick={copy}
              data-testid="copy-secret-btn"
              className="flex items-center gap-1 border border-gray-300 px-3 py-2 text-xs font-semibold hover:bg-gray-100"
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>

          <label className="mt-6 flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              data-testid="confirm-saved-checkbox"
              className="mt-1"
            />
            <span className="text-sm text-gray-700">
              I have stored this secret in a safe place (password manager /
              Windows Connector config).
            </span>
          </label>
        </div>

        <div className="flex justify-end border-t border-gray-200 px-6 py-4">
          <button
            onClick={onClose}
            disabled={!confirmed}
            data-testid="dismiss-secret-btn"
            className="bg-[#002FA7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#00227A] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
