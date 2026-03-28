/**
 * Tests for src/lib/api.ts
 * All network requests are mocked — no real HTTP calls are made.
 */
import { fetchProPlayers, getJobStatus, uploadVideo } from "@/lib/api";
import type { JobStatusResponse, ProPlayer } from "@/types/analysis";

const TOKEN = "test-jwt-token";
const BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(body: unknown, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: jest.fn().mockResolvedValue(body),
  } as unknown as Response);
}

function mockFetchError(body: unknown, status: number) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status,
    json: jest.fn().mockResolvedValue(body),
  } as unknown as Response);
}

afterEach(() => jest.resetAllMocks());

// ---------------------------------------------------------------------------
// fetchProPlayers
// ---------------------------------------------------------------------------

describe("fetchProPlayers", () => {
  const PLAYERS: ProPlayer[] = [
    { id: "p1", name: "Carlos Alcaraz", gender: "atp", thumbnail_url: "https://s3.example.com/a.jpg", shot_types: ["serve", "forehand"] },
  ];

  it("calls GET /api/v1/pro-players with auth header", async () => {
    mockFetch({ players: PLAYERS });
    await fetchProPlayers(TOKEN);
    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/api/v1/pro-players`,
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }) }),
    );
  });

  it("returns players array", async () => {
    mockFetch({ players: PLAYERS });
    const result = await fetchProPlayers(TOKEN);
    expect(result).toEqual(PLAYERS);
  });

  it("appends shot_type query param when provided", async () => {
    mockFetch({ players: PLAYERS });
    await fetchProPlayers(TOKEN, "serve");
    const url = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(url).toContain("shot_type=serve");
  });

  it("does not append query param when shotType is undefined", async () => {
    mockFetch({ players: PLAYERS });
    await fetchProPlayers(TOKEN, undefined);
    const url = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(url).not.toContain("shot_type");
  });

  it("throws with status and detail on 401", async () => {
    mockFetchError({ detail: "Invalid token" }, 401);
    await expect(fetchProPlayers(TOKEN)).rejects.toMatchObject({ status: 401, detail: "Invalid token" });
  });

  it("throws on 500 server error", async () => {
    mockFetchError({ detail: "Internal server error" }, 500);
    await expect(fetchProPlayers(TOKEN)).rejects.toMatchObject({ status: 500 });
  });

  it("returns empty array when players list is empty", async () => {
    mockFetch({ players: [] });
    const result = await fetchProPlayers(TOKEN);
    expect(result).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getJobStatus
// ---------------------------------------------------------------------------

describe("getJobStatus", () => {
  const STATUS: JobStatusResponse = {
    job_id: "job-123",
    status: "processing",
    progress_pct: 50,
    stage: "pose_extraction",
  };

  it("calls GET /api/v1/analysis/{jobId}/status", async () => {
    mockFetch(STATUS);
    await getJobStatus(TOKEN, "job-123");
    const url = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(url).toContain("/api/v1/analysis/job-123/status");
  });

  it("returns job status object", async () => {
    mockFetch(STATUS);
    const result = await getJobStatus(TOKEN, "job-123");
    expect(result).toEqual(STATUS);
  });

  it("includes auth header", async () => {
    mockFetch(STATUS);
    await getJobStatus(TOKEN, "job-123");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }) }),
    );
  });

  it("throws on 404 not found", async () => {
    mockFetchError({ detail: "Job not found" }, 404);
    await expect(getJobStatus(TOKEN, "bad-id")).rejects.toMatchObject({ status: 404 });
  });

  it("returns complete status with report_id", async () => {
    const complete = { ...STATUS, status: "complete" as const, stage: "complete" as const, progress_pct: 100, report_id: "report-abc" };
    mockFetch(complete);
    const result = await getJobStatus(TOKEN, "job-123");
    expect(result.report_id).toBe("report-abc");
  });

  it("returns warning_code when present", async () => {
    const withWarning = { ...STATUS, warning_code: "WARNING_POOR_ANGLE" };
    mockFetch(withWarning);
    const result = await getJobStatus(TOKEN, "job-123");
    expect(result.warning_code).toBe("WARNING_POOR_ANGLE");
  });
});

// ---------------------------------------------------------------------------
// uploadVideo — uses XHR, mock differently
// ---------------------------------------------------------------------------

describe("uploadVideo", () => {
  let xhrMock: {
    open: jest.Mock; setRequestHeader: jest.Mock; send: jest.Mock;
    onload: ((e: ProgressEvent) => void) | null;
    onerror: ((e: ProgressEvent) => void) | null;
    upload: { onprogress: ((e: ProgressEvent) => void) | null };
    status: number; responseText: string;
  };

  beforeEach(() => {
    xhrMock = {
      open: jest.fn(), setRequestHeader: jest.fn(), send: jest.fn(),
      onload: null, onerror: null,
      upload: { onprogress: null },
      status: 202,
      responseText: JSON.stringify({ job_id: "job-999", status: "queued", estimated_wait_seconds: 90 }),
    };
    (global as unknown as { XMLHttpRequest: unknown }).XMLHttpRequest = jest.fn(() => xhrMock);
  });

  afterEach(() => jest.restoreAllMocks());

  function triggerLoad() {
    xhrMock.onload?.(new ProgressEvent("load"));
  }

  it("resolves with upload response on 202", async () => {
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1");
    triggerLoad();
    const result = await promise;
    expect(result.job_id).toBe("job-999");
    expect(result.status).toBe("queued");
  });

  it("sends to correct URL", async () => {
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1");
    triggerLoad();
    await promise;
    expect(xhrMock.open).toHaveBeenCalledWith("POST", `${BASE}/api/v1/analysis/upload`);
  });

  it("sets Authorization header", async () => {
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1");
    triggerLoad();
    await promise;
    expect(xhrMock.setRequestHeader).toHaveBeenCalledWith("Authorization", `Bearer ${TOKEN}`);
  });

  it("calls onProgress with percentage", async () => {
    const onProgress = jest.fn();
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1", onProgress);
    // Simulate progress event
    xhrMock.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 } as ProgressEvent);
    triggerLoad();
    await promise;
    expect(onProgress).toHaveBeenCalledWith(50);
  });

  it("does not call onProgress when length not computable", async () => {
    const onProgress = jest.fn();
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1", onProgress);
    xhrMock.upload.onprogress?.({ lengthComputable: false, loaded: 0, total: 0 } as ProgressEvent);
    triggerLoad();
    await promise;
    expect(onProgress).not.toHaveBeenCalled();
  });

  it("rejects with parsed error on non-202 status", async () => {
    xhrMock.status = 402;
    xhrMock.responseText = JSON.stringify({ detail: { code: "UPLOAD_LIMIT_REACHED" } });
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1");
    triggerLoad();
    await expect(promise).rejects.toMatchObject({ detail: { code: "UPLOAD_LIMIT_REACHED" } });
  });

  it("rejects with status on network error", async () => {
    const file = new File([new ArrayBuffer(100)], "serve.mp4", { type: "video/mp4" });
    const promise = uploadVideo(TOKEN, file, "serve", "player-1");
    xhrMock.onerror?.(new ProgressEvent("error"));
    await expect(promise).rejects.toMatchObject({ status: 0, message: "Network error" });
  });
});
