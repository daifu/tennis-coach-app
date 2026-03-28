"use client";

import type { ShotType } from "@/types/analysis";

const SHOT_TYPES: { value: ShotType; label: string }[] = [
  { value: "serve", label: "Serve" },
  { value: "forehand", label: "Forehand" },
];

interface Props {
  value: ShotType;
  onChange: (v: ShotType) => void;
}

export default function ShotTypeSelector({ value, onChange }: Props) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Shot type
      </h2>
      <div className="flex gap-3">
        {SHOT_TYPES.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => onChange(s.value)}
            className={`px-6 py-3 rounded-xl font-medium transition-colors ${
              value === s.value
                ? "bg-green-500 text-white shadow-sm"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
