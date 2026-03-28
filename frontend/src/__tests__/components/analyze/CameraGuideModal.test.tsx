import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CameraGuideModal from "@/components/analyze/CameraGuideModal";

describe("CameraGuideModal", () => {
  it("renders the modal title", () => {
    render(<CameraGuideModal onConfirm={jest.fn()} onClose={jest.fn()} />);
    expect(screen.getByText(/camera placement tips/i)).toBeInTheDocument();
  });

  it("renders all four camera tips", () => {
    render(<CameraGuideModal onConfirm={jest.fn()} onClose={jest.fn()} />);
    expect(screen.getByText(/side-on view/i)).toBeInTheDocument();
    expect(screen.getByText(/hip height/i)).toBeInTheDocument();
    expect(screen.getByText(/10.{1,5}15 feet/i)).toBeInTheDocument();
    expect(screen.getByText(/good lighting/i)).toBeInTheDocument();
  });

  it("renders Cancel and confirm buttons", () => {
    render(<CameraGuideModal onConfirm={jest.fn()} onClose={jest.fn()} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /got it/i })).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = jest.fn();
    render(<CameraGuideModal onConfirm={jest.fn()} onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onConfirm when confirm button is clicked", async () => {
    const onConfirm = jest.fn();
    render(<CameraGuideModal onConfirm={onConfirm} onClose={jest.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /got it/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("does not call onConfirm when Cancel is clicked", async () => {
    const onConfirm = jest.fn();
    render(<CameraGuideModal onConfirm={onConfirm} onClose={jest.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("does not call onClose when confirm button is clicked", async () => {
    const onClose = jest.fn();
    render(<CameraGuideModal onConfirm={jest.fn()} onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /got it/i }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders with a backdrop overlay", () => {
    const { container } = render(<CameraGuideModal onConfirm={jest.fn()} onClose={jest.fn()} />);
    // The outer div should have the bg-black/50 overlay class
    const backdrop = container.firstChild as HTMLElement;
    expect(backdrop.className).toMatch(/bg-black/);
  });
});
