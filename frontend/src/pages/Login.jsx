import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";

const BG_URL =
  "https://static.prod-images.emergentagent.com/jobs/57dafff3-9277-4df6-9ac8-0567f8fd084f/images/ee4b6ce41eeaac837c5e44926f26547279b9247dc76e6f0bc95ce264069b0e89.png";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal masuk");
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (em) => {
    setEmail(em);
    setPassword("demo123");
  };

  return (
    <div className="min-h-screen bg-zinc-50 grid lg:grid-cols-2" data-testid="login-page">
      {/* Left – Brand */}
      <div className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-90"
          style={{ backgroundImage: `url(${BG_URL})` }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-zinc-50/30 to-zinc-50/10" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-12">
            <div className="w-9 h-9 bg-zinc-900 text-white flex items-center justify-center rounded-sm">
              <Sparkles size={18} />
            </div>
            <div className="font-heading text-base font-semibold tracking-tight">Semantic CV</div>
          </div>
          <h1 className="font-heading text-5xl font-semibold tracking-tight leading-tight max-w-md text-zinc-900">
            Penapisan CV dengan kecerdasan semantik.
          </h1>
          <p className="mt-6 text-zinc-700 max-w-sm">
            Otomatiskan seleksi kandidat, kurangi bias, dan ambil keputusan yang dapat diaudit
            dalam hitungan menit — bukan jam.
          </p>
        </div>
        <div className="relative text-xs text-zinc-600 font-mono">
          v1.0 · Internal HR Platform
        </div>
      </div>

      {/* Right – Form */}
      <div className="flex items-center justify-center p-8 lg:p-16 bg-white border-l border-zinc-200">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-zinc-900 text-white flex items-center justify-center rounded-sm">
              <Sparkles size={16} />
            </div>
            <div className="font-heading font-semibold">Semantic CV</div>
          </div>
          <h2 className="font-heading text-3xl font-semibold tracking-tight" data-testid="login-title">
            Masuk
          </h2>
          <p className="mt-2 text-sm text-zinc-500">Gunakan kredensial internal Anda.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" data-testid="login-form">
            <div>
              <Label htmlFor="email" className="text-xs font-medium text-zinc-700 uppercase tracking-wide">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nama@perusahaan.id"
                required
                data-testid="login-email-input"
                className="mt-2 rounded-sm border-zinc-300 focus-visible:ring-zinc-900"
              />
            </div>
            <div>
              <Label htmlFor="password" className="text-xs font-medium text-zinc-700 uppercase tracking-wide">
                Kata Sandi
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                data-testid="login-password-input"
                className="mt-2 rounded-sm border-zinc-300 focus-visible:ring-zinc-900"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              data-testid="login-submit-button"
              className="w-full rounded-sm bg-zinc-900 hover:bg-zinc-800 text-white h-10"
            >
              {loading ? "Memproses..." : "Masuk"}
            </Button>
          </form>

          <div className="mt-10 pt-6 border-t border-zinc-200">
            <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium mb-3">
              Akun Demo
            </div>
            <div className="space-y-2">
              {[
                { email: "hr@demo.com", role: "HR Recruiter" },
                { email: "manager@demo.com", role: "Hiring Manager" },
                { email: "admin@demo.com", role: "Admin IT" },
              ].map((d) => (
                <button
                  key={d.email}
                  type="button"
                  onClick={() => fillDemo(d.email)}
                  data-testid={`demo-account-${d.email.split("@")[0]}`}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs border border-zinc-200 hover:border-zinc-900 hover:bg-zinc-50 rounded-sm text-left transition-colors"
                >
                  <span className="font-mono text-zinc-700">{d.email}</span>
                  <span className="text-zinc-500">{d.role}</span>
                </button>
              ))}
              <div className="text-xs text-zinc-400 font-mono pt-1">Password: demo123</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
