import React from "react";
import { render, screen } from "@testing-library/react";
import UploadProgressBar from "@/components/analyze/UploadProgressBar";

describe("UploadProgressBar", () => {
  it("renders the filename", () => {
    render(<UploadProgressBar pct={50} filename="my-serve.mp4" />);
    expect(screen.getByText("my-serve.mp4")).toBeInTheDocument();
  });

  it("renders the percentage text", () => {
    render(<UploadProgressBar pct={73} filename="video.mp4" />);
    expect(screen.getByText("73%")).toBeInTheDocument();
  });

  it("renders 0%", () => {
    render(<UploadProgressBar pct={0} filename="video.mp4" />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("renders 100%", () => {
    render(<UploadProgressBar pct={100} filename="video.mp4" />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("progress bar fill width reflects pct prop", () => {
    const { container } = render(<UploadProgressBar pct={40} filename="video.mp4" />);
    const fill = container.querySelector<HTMLElement>(".bg-green-500");
    expect(fill?.style.width).toBe("40%");
  });

  it("progress bar fill width is 0% at start", () => {
    const { container } = render(<UploadProgressBar pct={0} filename="video.mp4" />);
    const fill = container.querySelector<HTMLElement>(".bg-green-500");
    expect(fill?.style.width).toBe("0%");
  });

  it("progress bar fill width is 100% when complete", () => {
    const { container } = render(<UploadProgressBar pct={100} filename="video.mp4" />);
    const fill = container.querySelector<HTMLElement>(".bg-green-500");
    expect(fill?.style.width).toBe("100%");
  });

  it("renders long filename without error", () => {
    const long = "a".repeat(200) + ".mp4";
    render(<UploadProgressBar pct={50} filename={long} />);
    expect(screen.getByText(long)).toBeInTheDocument();
  });
});
