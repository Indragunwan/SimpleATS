import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, Check, X, Pause, Mail, Phone } from "lucide-react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

const DIM_LABELS = {
  must_have: "Must-Have",
  experience: "Pengalaman",
  domain: "Domain",
  education: "Pendidikan",
  nice_have: "Nice-to-Have",
};

export default function ScreeningDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/screenings/${id}`);
    setData(data);
  };

  useEffect(() => {
    load();
  }, [id]);

  const setDecision = async (decision) => {
    try {
      await api.patch(`/screenings/${id}/decision`, { decision });
      toast.success(`Keputusan: ${decision}`);
      load();
    } catch (err) {
      toast.error("Gagal menyimpan keputusan");
    }
  };

  if (!data) return <div className="p-10 text-zinc-500" data-testid="screening-loading">Memuat...</div>;

  const { screening: s, candidate: c, job } = data;
  const band = SCORE_BAND(s.total_score);
  const parsed = c?.parsed || {};

  const radarData = [
    { dim: "Must", value: s.must_have.score, fullMark: 100 },
    { dim: "Pengalaman", value: s.experience.score, fullMark: 100 },
    { dim: "Domain", value: s.domain.score, fullMark: 100 },
    { dim: "Pendidikan", value: s.education.score, fullMark: 100 },
    { dim: "Nice", value: s.nice_have.score, fullMark: 100 },
  ];

  return (
    <div className="p-10" data-testid="screening-detail-page">
      <button
        onClick={() => navigate(`/jobs/${job.id}`)}
        className="text-xs text-zinc-500 hover:text-zinc-900 inline-flex items-center gap-1 mb-4"
        data-testid="back-to-job"
      >
        <ArrowLeft size={12} /> Kembali ke {job.title}
      </button>

      {/* Header */}
      <div className="bg-white border border-zinc-200 rounded-sm p-6 mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 bg-zinc-900 text-white flex items-center justify-center rounded-sm font-heading text-xl font-semibold">
            {(c?.name || "?").split(" ").map((n) => n[0]).slice(0, 2).join("")}
          </div>
          <div>
            <h1 className="font-heading text-2xl font-semibold tracking-tight" data-testid="candidate-name">
              {c?.name || "Tidak Diketahui"}
            </h1>
            <div className="text-sm text-zinc-500 mt-1 flex items-center gap-4 flex-wrap">
              {c?.email && (
                <span className="inline-flex items-center gap-1"><Mail size={12} />{c.email}</span>
              )}
              {c?.phone && (
                <span className="inline-flex items-center gap-1"><Phone size={12} />{c.phone}</span>
              )}
              <span className="text-xs">· {parsed.years_of_experience || 0} thn pengalaman</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs uppercase tracking-wider text-zinc-500">Skor Total</div>
            <div
              className={`font-heading text-5xl font-semibold tabular-nums mt-1 ${
                band === "high" ? "text-emerald-700" : band === "mid" ? "text-amber-700" : "text-rose-700"
              }`}
              data-testid="total-score"
            >
              {s.total_score}
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              Rekomendasi:{" "}
              <span className="font-medium text-zinc-900">
                {RECOMMENDATION_LABELS[s.recommendation]}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Decision Actions */}
      <div className="bg-white border border-zinc-200 rounded-sm p-4 mb-4 flex items-center justify-between" data-testid="decision-bar">
        <div className="text-sm">
          <span className="text-zinc-500">Keputusan saat ini: </span>
          <span className="font-medium" data-testid="current-decision">{s.decision}</span>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setDecision("shortlisted")}
            className="rounded-sm bg-emerald-600 hover:bg-emerald-700 text-white"
            size="sm"
            data-testid="decision-shortlist"
          >
            <Check size={14} className="mr-1" /> Daftar Pendek
          </Button>
          <Button
            onClick={() => setDecision("hold")}
            variant="outline"
            className="rounded-sm border-zinc-300"
            size="sm"
            data-testid="decision-hold"
          >
            <Pause size={14} className="mr-1" /> Tahan
          </Button>
          <Button
            onClick={() => setDecision("rejected")}
            className="rounded-sm bg-rose-600 hover:bg-rose-700 text-white"
            size="sm"
            data-testid="decision-reject"
          >
            <X size={14} className="mr-1" /> Tolak
          </Button>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Radar + Dimensions */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white border border-zinc-200 rounded-sm p-5">
            <div className="text-xs uppercase tracking-wider text-zinc-500 mb-3">
              Profil Skor 5 Dimensi
            </div>
            <div className="h-56" data-testid="radar-chart">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e4e4e7" />
                  <PolarAngleAxis dataKey="dim" tick={{ fontSize: 10, fill: "#52525b" }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar dataKey="value" stroke="#18181b" fill="#18181b" fillOpacity={0.15} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white border border-zinc-200 rounded-sm p-5 space-y-3">
            <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">
              Skor per Dimensi
            </div>
            {Object.entries(DIM_LABELS).map(([k, label]) => {
              const dim = s[k];
              const dband = SCORE_BAND(dim.score);
              return (
                <div key={k} data-testid={`dim-${k}`}>
                  <div className="flex justify-between items-baseline mb-1">
                    <span className="text-xs">{label}</span>
                    <span className={`text-xs font-mono font-semibold tabular-nums ${
                      dband === "high" ? "text-emerald-700" : dband === "mid" ? "text-amber-700" : "text-rose-700"
                    }`}>
                      {dim.score}
                    </span>
                  </div>
                  <div className="h-1 bg-zinc-100 rounded-sm overflow-hidden">
                    <div
                      className={
                        dband === "high"
                          ? "h-full bg-emerald-500"
                          : dband === "mid"
                          ? "h-full bg-amber-500"
                          : "h-full bg-rose-500"
                      }
                      style={{ width: `${dim.score}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Middle - CV Profile */}
        <div className="lg:col-span-2 bg-white border border-zinc-200 rounded-sm p-6" data-testid="cv-profile">
          <h3 className="font-heading text-base font-semibold tracking-tight mb-4">
            Profil Kandidat
          </h3>

          {parsed.summary && (
            <p className="text-sm text-zinc-700 mb-6 leading-relaxed">{parsed.summary}</p>
          )}

          {parsed.skills?.length > 0 && (
            <Section title="Keahlian">
              <div className="flex flex-wrap gap-1.5">
                {parsed.skills.map((sk, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-zinc-100 text-zinc-700 rounded-sm">
                    {sk}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {parsed.work_history?.length > 0 && (
            <Section title="Riwayat Pekerjaan">
              <div className="space-y-3">
                {parsed.work_history.map((w, i) => (
                  <div key={i} className="border-l-2 border-zinc-200 pl-3" data-testid={`work-${i}`}>
                    <div className="font-medium text-sm">{w.position}</div>
                    <div className="text-xs text-zinc-500">
                      {w.company} · {w.duration}
                    </div>
                    {w.achievements?.length > 0 && (
                      <ul className="mt-1 text-xs text-zinc-600 list-disc pl-4 space-y-0.5">
                        {w.achievements.slice(0, 3).map((a, j) => (
                          <li key={j}>{a}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {parsed.education?.length > 0 && (
            <Section title="Pendidikan">
              <div className="space-y-2">
                {parsed.education.map((e, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium">{e.degree}</div>
                    <div className="text-xs text-zinc-500">
                      {e.institution} · {e.year}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {parsed.certifications?.length > 0 && (
            <Section title="Sertifikasi">
              <ul className="text-sm text-zinc-700 list-disc pl-4 space-y-0.5">
                {parsed.certifications.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        {/* Right - Rationale */}
        <div className="lg:col-span-1 space-y-4">
          <div
            className="bg-zinc-50 border border-zinc-200 border-l-2 border-l-zinc-900 rounded-sm p-5"
            data-testid="rationale-panel"
          >
            <div className="text-xs uppercase tracking-wider text-zinc-500 mb-3 font-medium">
              Rationale AI
            </div>
            <p className="text-sm text-zinc-800 leading-relaxed" data-testid="rationale-summary">
              {s.rationale_summary || "—"}
            </p>
          </div>

          {s.strengths?.length > 0 && (
            <div className="bg-white border border-zinc-200 rounded-sm p-5" data-testid="strengths-panel">
              <div className="text-xs uppercase tracking-wider text-emerald-700 mb-3 font-medium">
                Kekuatan
              </div>
              <ul className="text-sm text-zinc-800 space-y-2">
                {s.strengths.map((str, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-emerald-600 mt-0.5">+</span>
                    <span>{str}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {s.gaps_summary?.length > 0 && (
            <div className="bg-white border border-zinc-200 rounded-sm p-5" data-testid="gaps-panel">
              <div className="text-xs uppercase tracking-wider text-rose-700 mb-3 font-medium">
                Kekurangan
              </div>
              <ul className="text-sm text-zinc-800 space-y-2">
                {s.gaps_summary.map((g, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-rose-600 mt-0.5">−</span>
                    <span>{g}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mb-5">
      <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2 font-medium">
        {title}
      </div>
      {children}
    </div>
  );
}
