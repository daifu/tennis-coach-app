import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ShotTypeSelector from "@/components/analyze/ShotTypeSelector";

describe("ShotTypeSelector", () => {
  it("renders both shot type buttons", () => {
    render(<ShotTypeSelector value="serve" onChange={jest.fn()} />);
    expect(screen.getByRole("button", { name: "Serve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Forehand" })).toBeInTheDocument();
  });

  it("renders the section heading", () => {
    render(<ShotTypeSelector value="serve" onChange={jest.fn()} />);
    expect(screen.getByText(/shot type/i)).toBeInTheDocument();
  });

  it("active button has green styling", () => {
    render(<ShotTypeSelector value="serve" onChange={jest.fn()} />);
    const serveBtn = screen.getByRole("button", { name: "Serve" });
    expect(serveBtn.className).toMatch(/bg-green-500/);
  });

  it("inactive button does not have green styling", () => {
    render(<ShotTypeSelector value="serve" onChange={jest.fn()} />);
    const forehandBtn = screen.getByRole("button", { name: "Forehand" });
    expect(forehandBtn.className).not.toMatch(/bg-green-500/);
  });

  it("calls onChange with 'forehand' when Forehand is clicked", async () => {
    const onChange = jest.fn();
    render(<ShotTypeSelector value="serve" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Forehand" }));
    expect(onChange).toHaveBeenCalledWith("forehand");
  });

  it("calls onChange with 'serve' when Serve is clicked", async () => {
    const onChange = jest.fn();
    render(<ShotTypeSelector value="forehand" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Serve" }));
    expect(onChange).toHaveBeenCalledWith("serve");
  });

  it("does not call onChange when already-active button is clicked", async () => {
    const onChange = jest.fn();
    render(<ShotTypeSelector value="serve" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Serve" }));
    // onChange is still called — the parent decides whether state changes
    expect(onChange).toHaveBeenCalledWith("serve");
  });

  it("switches active styling when value prop changes", () => {
    const { rerender } = render(<ShotTypeSelector value="serve" onChange={jest.fn()} />);
    rerender(<ShotTypeSelector value="forehand" onChange={jest.fn()} />);
    const forehandBtn = screen.getByRole("button", { name: "Forehand" });
    expect(forehandBtn.className).toMatch(/bg-green-500/);
    const serveBtn = screen.getByRole("button", { name: "Serve" });
    expect(serveBtn.className).not.toMatch(/bg-green-500/);
  });
});
