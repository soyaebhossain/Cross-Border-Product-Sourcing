import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Card from "../../components/common/Card.jsx";
import Input from "../../components/common/Input.jsx";
import Button from "../../components/common/Button.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";
import { useAuthStore } from "../../store/auth.store.js";

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setErr("");

    try {
      const res = await api.post(endpoints.auth.login, { identifier, password });

      setAuth({
        accessToken: res.data.access,
        refreshToken: res.data.refresh,
        user: res.data.user,
        roles: res.data.roles || [],
      });

      navigate("/");
    } catch (error) {
      setErr("Login failed. Check email/phone & password.");
    }
  };

  const handleSocial = async (provider) => {
    try {
      const res = await api.get(endpoints.auth.socialStart(provider));
      const url = res.data?.auth_url;
      if (url) {
        window.location.href = url;
      }
    } catch (e) {
      setErr("Social login not configured. Please use email/phone.");
    }
  };

  return (
    <div className="max-w-md mx-auto">
      <Card className="p-6 space-y-4">
        <div className="text-center space-y-1">
          <h1 className="text-xl font-semibold">Login</h1>
          <p className="text-gray-600 text-sm">Use email or phone number</p>
        </div>

        {err ? (
          <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-3">
            {err}
          </div>
        ) : null}

        <form className="space-y-3" onSubmit={submit}>
          <Input
            label="Email or Phone"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="example@email.com or 017xxxxxxxx"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />

          <Button className="w-full" type="submit">
            Login
          </Button>
        </form>

        <div className="text-sm text-gray-600 text-center">
          No account? <Link to="/signup" className="text-black underline">Create one</Link>
        </div>

        <div className="flex items-center gap-3">
          <span className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-500">or</span>
          <span className="flex-1 h-px bg-gray-200" />
        </div>

        <div className="space-y-2">
          <button
            type="button"
            onClick={() => handleSocial("google")}
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center justify-center gap-2"
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-full" style={{ background: "white", border: "1px solid #dadce0", color: "#4285F4", fontWeight: 700 }}>
              G
            </span>
            Continue with Google
          </button>
          <button
            type="button"
            onClick={() => handleSocial("facebook")}
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center justify-center gap-2"
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-sm" style={{ background: "#1877F2", color: "white", fontWeight: 700, fontSize: "12px" }}>
              f
            </span>
            Continue with Facebook
          </button>
        </div>
      </Card>
    </div>
  );
}
