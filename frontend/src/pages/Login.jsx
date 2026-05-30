import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";

const BG_URL =
  "https://static.prod-images.emergentagent.com/jobs/57dafff3-9277-4df6-9ac8-0567f8fd084f/images/ee4b6ce41eeaac837c5e44926f26547279b9247dc76e6f0bc95ce264069b0e89.png";

export default function Login() {
  const [loading, setLoading] = useState(false);
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);

    script.onload = () => {
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: process.env.REACT_APP_GOOGLE_CLIENT_ID || "",
          callback: handleGoogleLogin,
        });
        window.google.accounts.id.renderButton(
          document.getElementById("google-signin-btn"),
          { 
            theme: "outline", 
            size: "large", 
            width: "100%",
            text: "signin_with",
            shape: "square"
          }
        );
      }
    };

    return () => {
      document.body.removeChild(script);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGoogleLogin = async (response) => {
    setLoading(true);
    try {
      await loginWithGoogle(response.credential);
      navigate("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal masuk menggunakan Akun Google");
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
          <p className="mt-2 text-sm text-zinc-500 mb-8">
            Gunakan Akun Google Perusahaan Anda yang telah terdaftar untuk mengakses platform.
          </p>

          <div className="space-y-4">
            <div id="google-signin-btn" className="w-full min-h-[44px]" data-testid="google-login-button"></div>
            {loading && (
              <div className="text-center text-xs text-zinc-500 animate-pulse mt-2">
                Memverifikasi akun Google...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
