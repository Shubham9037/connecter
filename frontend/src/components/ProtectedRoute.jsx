import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="font-mono text-xs uppercase tracking-widest text-gray-500">
          Verifying session…
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="max-w-md border border-gray-200 p-8">
          <div className="font-heading text-2xl font-bold">Admin access required</div>
          <p className="mt-3 text-sm text-gray-600">
            Your account ({user.email}) is signed in, but not on the admin
            allowlist. Ask the workspace owner to add your email to
            <code className="mx-1 border border-gray-200 bg-gray-50 px-1 py-0.5">ADMIN_EMAILS</code>
            in the backend .env.
          </p>
        </div>
      </div>
    );
  }
  return children;
}
