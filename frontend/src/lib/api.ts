import type {
  JobHistoryResponse,
  JobStatusResponse,
  ProPlayer,
  ReportResponse,
  ShotType,
  UploadResponse,
} from "@/types/analysis";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authFetch(path: string, token: string, init?: RequestInit) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw { status: res.status, detail: body.detail ?? body };
  }
  return res.json();
}

export async function fetchProPlayers(token: string, shotType?: ShotType): Promise<ProPlayer[]> {
  const qs = shotType ? `?shot_type=${shotType}` : "";
  const data = await authFetch(`/api/v1/pro-players${qs}`, token);
  return data.players;
}

export async function uploadVideo(
  token: string,
  file: File,
  shotType: ShotType,
  proPlayerId: string,
  onProgress?: (pct: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("shot_type", shotType);
    form.append("pro_player_id", proPlayerId);
    form.append("video", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/api/v1/analysis/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status === 202) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          reject(JSON.parse(xhr.responseText));
        } catch {
          reject({ status: xhr.status });
        }
      }
    };

    xhr.onerror = () => reject({ status: 0, message: "Network error" });
    xhr.send(form);
  });
}

export async function getJobStatus(token: string, jobId: string): Promise<JobStatusResponse> {
  return authFetch(`/api/v1/analysis/${jobId}/status`, token);
}

export async function fetchReport(token: string, reportId: string): Promise<ReportResponse> {
  return authFetch(`/api/v1/reports/${reportId}`, token);
}

export async function fetchJobHistory(token: string): Promise<JobHistoryResponse> {
  return authFetch("/api/v1/users/me/jobs", token);
}
