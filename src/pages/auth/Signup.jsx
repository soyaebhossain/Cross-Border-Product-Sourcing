import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Card from "../../components/common/Card.jsx";
import Input from "../../components/common/Input.jsx";
import Button from "../../components/common/Button.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";
import { useAuthStore } from "../../store/auth.store.js";

export default function Signup() {
  const [form, setForm] = useState({ email: "", phone: "", username: "", password: "", role: "customer" });
  const [err, setErr] = useState("");
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const res = await api.post(endpoints.auth.register, {
        email: form.email || null,
        phone: form.phone || null,
        username: form.username || form.email || form.phone,
        password: form.password,
        role: form.role,
      });
      setAuth({
        accessToken: res.data.access,
        refreshToken: res.data.refresh,
        user: res.data.user,
        roles: res.data.user?.role ? [res.data.user.role] : [],
      });
      navigate("/");
    } catch (error) {
      setErr("Signup failed. Check required fields or try a different email/phone.");
    }
  };

  return (
    <div className="max-w-md mx-auto">
      <Card className="p-6">
        <h1 className="text-xl font-semibold">Create account</h1>
        <p className="text-gray-600 text-sm mt-1">Use email or phone to sign up.</p>

        {err ? (
          <div className="mt-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-3">
            {err}
          </div>
        ) : null}

        <form className="mt-4 space-y-3" onSubmit={submit}>
          <Input
            label="Email"
            value={form.email}
            onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
            placeholder="you@example.com"
          />
          <Input
            label="Phone"
            value={form.phone}
            onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))}
            placeholder="017xxxxxxxx"
          />
          <Input
            label="Username"
            value={form.username}
            onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
            placeholder="username (optional)"
          />
          <Input
            label="Password"
            type="password"
            value={form.password}
            onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
            placeholder="••••••••"
          />

          <Button className="w-full" type="submit">
            Sign up
          </Button>
        </form>

        <div className="mt-4 text-sm text-gray-600 text-center">
          Already have an account? <Link to="/login" className="text-black underline">Login</Link>
        </div>
      </Card>
    </div>
  );
}
