import { Link, NavLink, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/overview", label: "Overview", testid: "nav-overview" },
  { to: "/connectors", label: "Connectors", testid: "nav-connectors" },
  { to: "/logs", label: "Sync Logs", testid: "nav-logs" },
  { to: "/security", label: "Security", testid: "nav-security" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Top bar */}
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-6">
          <Link to="/overview" className="flex items-center gap-3" data-testid="brand-link">
            <div className="h-6 w-6 bg-[#002FA7]" />
            <div className="font-heading text-lg font-black tracking-tight">
              RAZIO CONNECT
            </div>
            <div className="border-l border-gray-200 pl-3 font-mono text-[11px] uppercase tracking-widest text-gray-500">
              Module 1A
            </div>
          </Link>

          <div className="flex items-center gap-4">
            {user && (
              <div className="flex items-center gap-3">
                {user.picture && (
                  <img
                    src={user.picture}
                    alt=""
                    className="h-7 w-7 border border-gray-200 object-cover"
                  />
                )}
                <div className="text-right">
                  <div className="text-xs font-semibold">{user.name}</div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-gray-500">
                    {user.email}
                  </div>
                </div>
              </div>
            )}
            <button
              onClick={handleLogout}
              data-testid="logout-btn"
              className="flex items-center gap-2 border border-gray-200 px-3 py-1.5 text-xs font-semibold uppercase tracking-widest text-gray-700 hover:bg-gray-50"
            >
              <LogOut className="h-3.5 w-3.5" /> Log out
            </button>
          </div>
        </div>

        {/* Sub-nav */}
        <nav className="border-t border-gray-200">
          <div className="mx-auto flex max-w-[1400px] gap-6 px-6">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                data-testid={item.testid}
                className={({ isActive }) =>
                  `border-b-2 py-3 text-xs font-bold uppercase tracking-[0.15em] transition-colors ${
                    isActive
                      ? "border-[#002FA7] text-[#002FA7]"
                      : "border-transparent text-gray-500 hover:text-gray-900"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>
    </div>
  );
}
