import { LOGIN } from "@/constants/testIds";

export default function Login() {
  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS,
    // THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/overview";
    window.location.href =
      "https://auth.emergentagent.com/?redirect=" + encodeURIComponent(redirectUrl);
  };

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-2">
      {/* Left — abstract visual */}
      <div className="hidden md:block relative">
        <img
          src="https://images.unsplash.com/photo-1595411425732-e69c1abe2763?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2ODl8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMHBhdHRlcm4lMjBibGFjayUyMGFuZCUyMHdoaXRlfGVufDB8fHx8MTc4MzA4MDUxNnww&ixlib=rb-4.1.0&q=85"
          alt=""
          className="h-full w-full object-cover"
        />
        <div className="absolute inset-0 flex flex-col justify-between p-10 text-white">
          <div className="font-mono text-[11px] uppercase tracking-[0.25em]">
            Razio / Connect
          </div>
          <div>
            <h1 className="font-heading text-4xl font-black leading-[1] tracking-tighter">
              Tally,
              <br /> hardened.
            </h1>
            <p className="mt-4 max-w-xs text-sm text-white/80">
              HMAC-signed sync. Replay-safe. Idempotent by design. Built for
              accountants who can&apos;t afford surprises.
            </p>
          </div>
        </div>
      </div>

      {/* Right — auth panel */}
      <div className="flex items-center justify-center px-8 py-16">
        <div className="w-full max-w-sm">
          <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-gray-500">
            Admin Console
          </div>
          <h2 className="mt-3 font-heading text-3xl font-black tracking-tighter text-gray-900">
            Sign in
          </h2>
          <p className="mt-3 text-sm text-gray-600">
            Access is restricted to allowlisted admin accounts. Continue with
            Google below.
          </p>

          <button
            onClick={handleGoogleLogin}
            data-testid={LOGIN.googleBtn}
            className="mt-8 flex w-full items-center justify-center gap-3 border border-gray-900 bg-white px-4 py-3 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-900 hover:text-white"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
              <path
                fill="currentColor"
                d="M21.35 11.1H12v2.98h5.35c-.23 1.5-1.62 4.4-5.35 4.4-3.22 0-5.85-2.68-5.85-5.98s2.63-5.98 5.85-5.98c1.83 0 3.06.78 3.76 1.45l2.56-2.47C16.68 3.9 14.55 3 12 3 6.98 3 3 6.98 3 12s3.98 9 9 9c5.2 0 8.63-3.65 8.63-8.8 0-.6-.07-1.03-.15-1.4Z"
              />
            </svg>
            Continue with Google
          </button>

          <div className="mt-10 border-t border-gray-200 pt-5 font-mono text-[10px] uppercase tracking-widest text-gray-500">
            v1.0.0-module1a &nbsp;/&nbsp; sha256-authenticated
          </div>
        </div>
      </div>
    </div>
  );
}
