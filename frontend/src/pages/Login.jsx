import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Heart } from "lucide-react";

const BG_URL =
  "https://static.prod-images.emergentagent.com/jobs/57dafff3-9277-4df6-9ac8-0567f8fd084f/images/ee4b6ce41eeaac837c5e44926f26547279b9247dc76e6f0bc95ce264069b0e89.png";

export default function Login() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      toast.error("Alamat email tidak boleh kosong");
      return;
    }
    setLoading(true);
    try {
      await login(cleanEmail);
      toast.success("Berhasil masuk!");
      navigate("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal masuk. Silakan periksa kembali email Anda.");
    } finally {
      setLoading(false);
    }
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
            <div className="w-9 h-9 bg-rose-600 text-white flex items-center justify-center rounded-sm">
              <Heart size={18} fill="currentColor" />
            </div>
            <div className="font-heading text-base font-semibold tracking-tight">HEARTH</div>
          </div>
          <h1 className="font-heading text-5xl font-semibold tracking-tight leading-tight max-w-md text-zinc-900">
            Human Resources Applicant Tracking.
          </h1>
          <p className="mt-6 text-zinc-700 max-w-sm">
            Otomatiskan seleksi kandidat dengan CV Screening System — kurangi bias, dan ambil keputusan yang dapat diaudit
            dalam hitungan menit.
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
            <div className="w-8 h-8 bg-rose-600 text-white flex items-center justify-center rounded-sm">
              <Heart size={16} fill="currentColor" />
            </div>
            <div className="font-heading font-semibold">HEARTH</div>
          </div>
          <h2 className="font-heading text-3xl font-semibold tracking-tight" data-testid="login-title">
            Masuk
          </h2>
          <p className="mt-2 text-sm text-zinc-500 mb-8">
            Masukkan alamat email perusahaan Anda yang telah terdaftar untuk masuk ke platform.
          </p>

          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-xs uppercase text-zinc-500 font-semibold tracking-wider">
                Alamat Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="nama@perusahaan.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="rounded-sm mt-1 focus:ring-rose-600 focus:border-rose-600"
                data-testid="email-input"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="w-full rounded-sm bg-rose-600 hover:bg-rose-700 text-white font-medium shadow-sm transition-colors py-2"
              data-testid="login-button"
            >
              {loading ? "Memverifikasi..." : "Masuk"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
