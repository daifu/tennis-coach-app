import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VideoDropzone from "@/components/analyze/VideoDropzone";

// Stub URL.createObjectURL / revokeObjectURL (not available in jsdom)
beforeAll(() => {
  global.URL.createObjectURL = jest.fn(() => "blob:fake-url");
  global.URL.revokeObjectURL = jest.fn();
});

// Helper: create a fake File with a duration attribute injected into
// the HTMLVideoElement that gets created during validation.
function mockVideoElement(duration: number, triggerLoad = true) {
  const origCreate = document.createElement.bind(document);
  jest.spyOn(document, "createElement").mockImplementation((tag: string) => {
    if (tag === "video") {
      const el = origCreate("video") as HTMLVideoElement;
      Object.defineProperty(el, "duration", { value: duration });
      if (triggerLoad) {
        setTimeout(() => el.onloadedmetadata?.(new Event("loadedmetadata")), 0);
      }
      return el;
    }
    return origCreate(tag);
  });
}

afterEach(() => jest.restoreAllMocks());

function makeFile(name: string, type: string, size = 1024): File {
  return new File([new ArrayBuffer(size)], name, { type });
}

describe("VideoDropzone", () => {
  it("renders the drop zone and instructions", () => {
    render(<VideoDropzone onFile={jest.fn()} />);
    expect(screen.getByText(/drop your video here/i)).toBeInTheDocument();
    expect(screen.getByText(/mp4 or mov/i)).toBeInTheDocument();
  });

  it("renders hidden file input", () => {
    const { container } = render(<VideoDropzone onFile={jest.fn()} />);
    // Input is rendered outside the dropzone div to prevent click-event bubbling
    const input = container.querySelector("input[type=file]");
    expect(input).toBeInTheDocument();
    expect(input).toHaveClass("hidden");
  });

  it("shows camera guide modal on click", async () => {
    render(<VideoDropzone onFile={jest.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/camera placement tips/i)).toBeInTheDocument();
  });

  it("does not show modal when disabled", async () => {
    render(<VideoDropzone onFile={jest.fn()} disabled />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.queryByText(/camera placement tips/i)).not.toBeInTheDocument();
  });

  it("closes modal and opens file picker on confirm", async () => {
    render(<VideoDropzone onFile={jest.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/camera placement tips/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /got it/i }));
    expect(screen.queryByText(/camera placement tips/i)).not.toBeInTheDocument();
  });

  it("closes modal on cancel", async () => {
    render(<VideoDropzone onFile={jest.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByText(/camera placement tips/i)).not.toBeInTheDocument();
  });

  it("shows error for non-video file type", async () => {
    const onFile = jest.fn();
    const { container } = render(<VideoDropzone onFile={onFile} />);
    const input = container.querySelector("input[type=file]")!;
    const file = makeFile("doc.pdf", "application/pdf");
    // Use fireEvent.change to bypass userEvent's pointer-event model which
    // can bubble into the dropzone div and open the modal unintentionally.
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await waitFor(() => {
      expect(screen.getByText(/only mp4 and mov/i)).toBeInTheDocument();
    });
    expect(onFile).not.toHaveBeenCalled();
  });

  it("shows error for video longer than 60s", async () => {
    mockVideoElement(90); // 90s > 60s limit
    const onFile = jest.fn();
    const { container } = render(<VideoDropzone onFile={onFile} />);
    const input = container.querySelector("input[type=file]")!;
    const file = makeFile("long.mp4", "video/mp4");
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await waitFor(() => {
      expect(screen.getByText(/90s/i)).toBeInTheDocument();
    });
    expect(onFile).not.toHaveBeenCalled();
  });

  it("calls onFile for valid mp4 within 60s", async () => {
    mockVideoElement(30);
    const onFile = jest.fn();
    const { container } = render(<VideoDropzone onFile={onFile} />);
    const input = container.querySelector("input[type=file]")!;
    const file = makeFile("serve.mp4", "video/mp4");
    await userEvent.upload(input, file);
    await waitFor(() => expect(onFile).toHaveBeenCalledWith(file));
  });

  it("calls onFile for valid mov within 60s", async () => {
    mockVideoElement(45);
    const onFile = jest.fn();
    const { container } = render(<VideoDropzone onFile={onFile} />);
    const input = container.querySelector("input[type=file]")!;
    const file = makeFile("clip.mov", "video/quicktime");
    await userEvent.upload(input, file);
    await waitFor(() => expect(onFile).toHaveBeenCalledWith(file));
  });

  it("accepts video exactly at 60s boundary", async () => {
    mockVideoElement(60);
    const onFile = jest.fn();
    const { container } = render(<VideoDropzone onFile={onFile} />);
    const input = container.querySelector("input[type=file]")!;
    const file = makeFile("clip.mp4", "video/mp4");
    await userEvent.upload(input, file);
    await waitFor(() => expect(onFile).toHaveBeenCalled());
  });

  it("dragOver changes border styling", () => {
    const { container } = render(<VideoDropzone onFile={jest.fn()} />);
    const dropzone = container.querySelector("[role=button]")!;
    fireEvent.dragOver(dropzone, { preventDefault: jest.fn() });
    expect(dropzone.className).toMatch(/border-green-400/);
  });

  it("dragLeave restores default border", () => {
    const { container } = render(<VideoDropzone onFile={jest.fn()} />);
    const dropzone = container.querySelector("[role=button]")!;
    fireEvent.dragOver(dropzone, { preventDefault: jest.fn() });
    fireEvent.dragLeave(dropzone);
    expect(dropzone.className).not.toMatch(/border-green-400/);
  });

  it("Enter key opens modal when not disabled", async () => {
    render(<VideoDropzone onFile={jest.fn()} />);
    const dropzone = screen.getByRole("button");
    fireEvent.keyDown(dropzone, { key: "Enter" });
    expect(screen.getByText(/camera placement tips/i)).toBeInTheDocument();
  });

  it("disabled dropzone has pointer-events-none class", () => {
    const { container } = render(<VideoDropzone onFile={jest.fn()} disabled />);
    const dropzone = container.querySelector("[role=button]")!;
    expect(dropzone.className).toMatch(/pointer-events-none/);
  });
});
