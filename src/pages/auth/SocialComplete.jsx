import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Card from "../../components/common/Card.jsx";
import { useAuthStore } from "../../store/auth.store.js";

export default function SocialComplete() {
  const { search } = useLocation();
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  useEffect(() => {
    const params = new URLSearchParams(search);
    const access = params.get("access");
    const refresh = params.get("refresh");
    if (access && refresh) {
      setAuth({ accessToken: access, refreshToken: refresh, user: null, roles: [] });
      navigate("/", { replace: true });
    }
  }, [search, setAuth, navigate]);

  return (
    <div className="max-w-md mx-auto">
      <Card className="p-6 text-center space-y-2">
        <div className="font-semibold text-lg">Completing social login…</div>
        <div className="text-sm text-gray-600">Redirecting to your account.</div>
      </Card>
    </div>
  );
}
