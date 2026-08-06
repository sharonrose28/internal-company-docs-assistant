import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";

export function ProtectedRoute() {
  const token = useAuthStore((state) => state.token);
  const location = useLocation();
  return token ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}
