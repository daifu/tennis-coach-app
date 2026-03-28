import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProPlayerPicker from "@/components/analyze/ProPlayerPicker";
import type { ProPlayer } from "@/types/analysis";

const PLAYERS: ProPlayer[] = [
  { id: "p1", name: "Carlos Alcaraz", gender: "atp", thumbnail_url: "https://s3.example.com/alcaraz.jpg", shot_types: ["serve", "forehand"] },
  { id: "p2", name: "Iga Swiatek",    gender: "wta", thumbnail_url: "https://s3.example.com/swiatek.jpg",  shot_types: ["serve", "forehand"] },
];

describe("ProPlayerPicker", () => {
  it("renders all players", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId={null} onSelect={jest.fn()} />);
    expect(screen.getByText("Carlos Alcaraz")).toBeInTheDocument();
    expect(screen.getByText("Iga Swiatek")).toBeInTheDocument();
  });

  it("shows empty-state message when no players", () => {
    render(<ProPlayerPicker players={[]} selectedId={null} onSelect={jest.fn()} />);
    expect(screen.getByText(/no players available/i)).toBeInTheDocument();
  });

  it("renders player gender badge", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId={null} onSelect={jest.fn()} />);
    expect(screen.getByText("atp")).toBeInTheDocument();
    expect(screen.getByText("wta")).toBeInTheDocument();
  });

  it("renders player thumbnail image", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId={null} onSelect={jest.fn()} />);
    const img = screen.getByAltText("Carlos Alcaraz");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://s3.example.com/alcaraz.jpg");
  });

  it("calls onSelect with player id when clicked", async () => {
    const onSelect = jest.fn();
    render(<ProPlayerPicker players={PLAYERS} selectedId={null} onSelect={onSelect} />);
    await userEvent.click(screen.getByText("Carlos Alcaraz").closest("button")!);
    expect(onSelect).toHaveBeenCalledWith("p1");
  });

  it("selected player button has green border", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId="p1" onSelect={jest.fn()} />);
    const btn = screen.getByText("Carlos Alcaraz").closest("button")!;
    expect(btn.className).toMatch(/border-green-500/);
  });

  it("unselected player button does not have green border", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId="p1" onSelect={jest.fn()} />);
    const btn = screen.getByText("Iga Swiatek").closest("button")!;
    expect(btn.className).not.toMatch(/border-green-500/);
  });

  it("no player selected — no button has green border", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId={null} onSelect={jest.fn()} />);
    PLAYERS.forEach((p) => {
      const btn = screen.getByText(p.name).closest("button")!;
      expect(btn.className).not.toMatch(/border-green-500/);
    });
  });

  it("clicking a different player calls onSelect with new id", async () => {
    const onSelect = jest.fn();
    render(<ProPlayerPicker players={PLAYERS} selectedId="p1" onSelect={onSelect} />);
    await userEvent.click(screen.getByText("Iga Swiatek").closest("button")!);
    expect(onSelect).toHaveBeenCalledWith("p2");
  });

  it("renders section heading", () => {
    render(<ProPlayerPicker players={PLAYERS} selectedId={null} onSelect={jest.fn()} />);
    expect(screen.getByText(/compare against/i)).toBeInTheDocument();
  });
});
