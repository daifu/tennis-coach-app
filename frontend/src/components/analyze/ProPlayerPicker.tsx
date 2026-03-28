"use client";

import Image from "next/image";
import type { ProPlayer } from "@/types/analysis";

interface Props {
  players: ProPlayer[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function ProPlayerPicker({ players, selectedId, onSelect }: Props) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Compare against
      </h2>
      {players.length === 0 ? (
        <p className="text-sm text-gray-400">No players available for this shot type.</p>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
          {players.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelect(p.id)}
              className={`flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-colors ${
                selectedId === p.id
                  ? "border-green-500 bg-green-50"
                  : "border-transparent bg-gray-100 hover:bg-gray-200"
              }`}
            >
              <div className="relative w-14 h-14 rounded-full overflow-hidden bg-gray-300">
                <Image
                  src={p.thumbnail_url}
                  alt={p.name}
                  fill
                  className="object-cover"
                  sizes="56px"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
              <span className="text-xs font-medium text-center text-gray-700 leading-tight">
                {p.name}
              </span>
              <span className="text-[10px] uppercase tracking-wide text-gray-400">
                {p.gender}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
