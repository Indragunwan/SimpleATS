import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";
import { ArrowLeft, Mail, Phone } from "lucide-react";

export default function TalentPoolDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get(`/talent-pool/${id}`).then((r) => setData(r.data));
  }, [id]);

  if (!data) return <div className="p-10 text-zinc-500">Memuat...</div>;
  const c = data.candidate;
  const parsed = c.parsed || {};
  const screenings = data.screenings || [];

  return (
    <div className="p-10" data-testid="pool-detail-page">
      <button
        onClick={() => navigate("/talent-pool")}
        className="text-xs text-zinc-500 hover:text-zinc-900 inline-flex items-center gap-1 mb-4"
        data-testid="back-to-pool"
      >
        <ArrowLeft size={12} /> Kembali ke Talent Pool
      </button>

      <div className="bg-white border border-zinc-200 rounded-sm p-6 mb-4">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 bg-zinc-900 text-white flex items-center justify-center rounded-sm font-heading text-xl font-semibold">
            {(c.name || "?").split(" ").map((n) => n[0]).slice(0, 2).join("")}
          </div>
          <div>
            <h1 className="font-heading text-2xl font-semibold tracking-tight">{c.name}</h1>
            <div className="text-sm text-zinc-500 mt-1 flex items-center gap-4 flex-wrap">
              {c.email && <span className="inline-flex items-center gap-1"><Mail size={12} />{c.email}</span>}
              {c.phone && <span className="inline-flex items-center gap-1"><Phone size={12} />{c.phone}</span>}
              <span className="text-xs">· {parsed.years_of_experience || 0} thn pengalaman</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-zinc-200 rounded-sm p-6">
          <h3 className="font-heading text-base font-semibold tracking-tight mb-4">Profil</h3>
          {parsed.summary && <p className="text-sm text-zinc-700 mb-5 leading-relaxed">{parsed.summary}</p>}

          {parsed.skills?.length > 0 && (
            <Section title="Keahlian">
              <div className="flex flex-wrap gap-1.5">
                {parsed.skills.map((s, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-zinc-100 text-zinc-700 rounded-sm">{s}</span>
                ))}
              </div>
            </Section>
          )}

          {parsed.work_history?.length > 0 && (
            <Section title="Riwayat Pekerjaan">
              <div className="space-y-3">
                {parsed.work_history.map((w, i) => (
                  <div key={i} className="border-l-2 border-zinc-200 pl-3">
                    <div className="font-medium text-sm">{w.position}</div>
                    <div className="text-xs text-zinc-500">{w.company} · {w.duration}</div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {parsed.education?.length > 0 && (
            <Section title="Pendidikan">
              {parsed.education.map((e, i) => (
                <div key={i} className="text-sm mb-1">
                  <div className="font-medium">{e.degree}</div>
                  <div className="text-xs text-zinc-500">{e.institution} · {e.year}</div>
                </div>
              ))}
            </Section>
          )}
        </div>

        <div className="lg:col-span-1 bg-white border border-zinc-200 rounded-sm p-6" data-testid="screening-history">
          <h3 className="font-heading text-base font-semibold tracking-tight mb-4">Riwayat Screening</h3>
          {screenings.length === 0 ? (
            <div className="text-sm text-zinc-400">Belum pernah di-screening</div>
          ) : (
            <div className="space-y-2">
              {screenings.map((s) => {
                const band = SCORE_BAND(s.total_score);
                return (
                  <button
                    key={s.id}
                    onClick={() => navigate(`/screenings/${s.id}`)}
                    data-testid={`history-screening-${s.id}`}
                    className="w-full text-left p-3 border border-zinc-200 hover:border-zinc-900 rounded-sm transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{s.job_title}</div>
                        <div className="text-xs text-zinc-500 mt-0.5">{s.job_department || "—"}</div>
                        <div className="text-xs text-zinc-500 mt-1">
                          {RECOMMENDATION_LABELS[s.recommendation]}
                          {s.decision !== "pending" && (
                            <span className="ml-2 text-zinc-900 font-medium">· {s.decision}</span>
                          )}
                        </div>
                      </div>
                      <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded-sm border ${BAND_COLORS[band]}`}>
                        {s.total_score}
                      </span>
                    </div>
                  </button>
                );
              })}
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
      <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2 font-medium">{title}</div>
      {children}
    </div>
  );
}
