"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchReport } from "@/lib/api";
import type { CoachingFlaw, JointAngleData, PhaseMetric, ReportResponse } from "@/types/analysis";

const TOKEN_PLACEHOLDER = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";

const JOINT_LABELS: Record<string, string> = {
  right_elbow: "Right elbow",
  left_elbow: "Left elbow",
  right_knee: "Right knee",
  left_knee: "Left knee",
  right_shoulder_abduction: "Shoulder abduction",
};

const PHASE_LABELS: Record<string, string> = {
  preparation: "Preparation",
  loading: "Loading",
  contact: "Contact",
  follow_through: "Follow-through",
};

function ScoreRing({ score }: { score: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - score / 100);
  const color = score >= 70 ? "#22c55e" : score >= 45 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="128" height="128" viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={r} fill="none" stroke="#e5e7eb" strokeWidth="12" />
        <circle
          cx="64" cy="64" r={r} fill="none"
          stroke={color} strokeWidth="12"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 64 64)"
        />
        <text x="64" y="64" dominantBaseline="middle" textAnchor="middle"
          className="font-bold" style={{ fontSize: 26, fill: color, fontWeight: 700 }}>
          {Math.round(score)}
        </text>
        <text x="64" y="82" dominantBaseline="middle" textAnchor="middle"
          style={{ fontSize: 11, fill: "#6b7280" }}>
          / 100
        </text>
      </svg>
      <p className="text-sm text-gray-500">Similarity score</p>
    </div>
  );
}

function JointAngleRow({ label, data }: { label: string; data: JointAngleData }) {
  const delta = data.delta_mean;
  const absDelta = Math.abs(delta);
  const isClose = absDelta < 5;
  const direction = delta > 0 ? "higher" : "lower";

  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-700 w-44">{label}</span>
      <div className="flex gap-6 text-sm text-right">
        <span className="w-16 text-gray-900 font-medium">{data.user_mean.toFixed(1)}°</span>
        <span className="w-16 text-gray-400">{data.pro_mean.toFixed(1)}°</span>
        <span className={`w-24 font-medium ${isClose ? "text-green-600" : "text-amber-600"}`}>
          {isClose ? "On target" : `${absDelta.toFixed(1)}° ${direction}`}
        </span>
      </div>
    </div>
  );
}

function PhaseBar({ phase, data }: { phase: string; data: PhaseMetric }) {
  const pct = data.similarity;
  const color = pct >= 70 ? "bg-green-500" : pct >= 45 ? "bg-amber-400" : "bg-red-400";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-700">{PHASE_LABELS[phase] ?? phase}</span>
        <span className="font-medium text-gray-900">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function FlawCard({ flaw }: { flaw: CoachingFlaw }) {
  return (
    <div className="rounded-2xl border border-gray-200 p-5 space-y-3">
      <div className="flex items-start gap-3">
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-100 text-green-700 text-xs font-bold flex items-center justify-center mt-0.5">
          {flaw.flaw_index}
        </span>
        <p className="text-gray-900 font-semibold text-sm leading-snug">{flaw.what}</p>
      </div>
      <div className="ml-9 space-y-2 text-sm text-gray-600">
        <p><span className="font-medium text-gray-800">Why it matters: </span>{flaw.why}</p>
        <p className="bg-green-50 rounded-xl px-3 py-2 text-green-800">
          <span className="font-medium">Fix: </span>{flaw.fix_drill}
        </p>
      </div>
    </div>
  );
}

export default function ReportPage() {
  const params = useParams();
  const router = useRouter();
  const reportId = params.report_id as string;

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reportId) return;
    fetchReport(TOKEN_PLACEHOLDER, reportId)
      .then(setReport)
      .catch(() => setError("Report not found."))
      .finally(() => setLoading(false));
  }, [reportId]);

  if (loading) {
    return (
      <main className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-gray-500 text-sm">Loading report...</p>
        </div>
      </main>
    );
  }

  if (error || !report) {
    return (
      <main className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-gray-700">{error ?? "Report not found."}</p>
          <button onClick={() => router.push("/")} className="text-sm text-green-600 underline">
            Go home
          </button>
        </div>
      </main>
    );
  }

  const shotLabel = report.shot_type.charAt(0).toUpperCase() + report.shot_type.slice(1);

  return (
    <main className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-10">
        {/* Header */}
        <div>
          <button onClick={() => router.push("/history")} className="text-xs text-gray-400 hover:text-gray-600 mb-4 block">
            ← Back to history
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{shotLabel} analysis</h1>
          <p className="mt-1 text-gray-500 text-sm">
            vs {report.pro_player_name} &middot;{" "}
            {new Date(report.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
          </p>
        </div>

        {/* Poor angle warning */}
        {report.warning_code === "WARNING_POOR_ANGLE" && (
          <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
            Camera angle may affect accuracy. For best results, film from the side at hip height, 10–15 feet away.
          </div>
        )}

        {/* Similarity score */}
        <div className="flex flex-col items-center">
          <ScoreRing score={report.similarity_score} />
        </div>

        {/* Phase breakdown */}
        {Object.keys(report.phase_metrics).length > 0 && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Phase breakdown</h2>
            <div className="rounded-2xl border border-gray-200 p-5 space-y-4">
              {Object.entries(report.phase_metrics).map(([phase, data]) => (
                <PhaseBar key={phase} phase={phase} data={data as PhaseMetric} />
              ))}
            </div>
          </section>
        )}

        {/* Joint angles */}
        {Object.keys(report.joint_angles).length > 0 && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Joint angles</h2>
            <div className="rounded-2xl border border-gray-200 px-5">
              <div className="flex justify-end gap-6 py-2 text-xs text-gray-400 border-b border-gray-100">
                <span className="w-16 text-right">You</span>
                <span className="w-16 text-right">Pro</span>
                <span className="w-24 text-right">Difference</span>
              </div>
              {Object.entries(report.joint_angles).map(([joint, data]) => (
                <JointAngleRow
                  key={joint}
                  label={JOINT_LABELS[joint] ?? joint}
                  data={data as JointAngleData}
                />
              ))}
            </div>
          </section>
        )}

        {/* Coaching feedback */}
        {report.coaching_feedback.length > 0 && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
              Coaching feedback
            </h2>
            <div className="space-y-3">
              {report.coaching_feedback
                .sort((a, b) => a.impact_order - b.impact_order)
                .map((flaw) => (
                  <FlawCard key={flaw.flaw_index} flaw={flaw} />
                ))}
            </div>
          </section>
        )}

        {/* CTA */}
        <div className="flex gap-3">
          <button
            onClick={() => router.push("/analyze/new")}
            className="flex-1 py-4 rounded-2xl bg-green-500 text-white font-semibold text-base
              hover:bg-green-600 transition-colors"
          >
            Analyze another stroke
          </button>
          <button
            onClick={() => router.push("/history")}
            className="py-4 px-6 rounded-2xl border border-gray-200 text-gray-700 font-semibold text-base
              hover:bg-gray-50 transition-colors"
          >
            History
          </button>
        </div>
      </div>
    </main>
  );
}
