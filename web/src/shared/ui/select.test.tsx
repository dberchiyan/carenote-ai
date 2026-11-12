import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { matches, Select, type SelectOption } from "./select";

const VITALS: SelectOption[] = [
  { value: "heart_rate", label: "Heart rate", hint: "/min" },
  { value: "spo2", label: "SpO₂", hint: "%" },
  { value: "temperature", label: "Temperature", hint: "°C" },
  { value: "weight", label: "Weight", hint: "kg", disabled: true },
];

function Harness({
  options = VITALS,
  initial = "spo2",
}: {
  options?: SelectOption[];
  initial?: string;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <label htmlFor="vital">Vital sign</label>
      <Select id="vital" value={value} onChange={setValue} options={options} />
      <output>{value}</output>
    </>
  );
}

describe("Select", () => {
  it("is a labelled combobox showing the selected option", () => {
    render(<Harness />);
    const box = screen.getByRole("combobox", { name: "Vital sign" });
    expect(box).toHaveTextContent("SpO₂");
    expect(box).toHaveAttribute("aria-expanded", "false");
  });

  it("opens on click, ticks the selected option and chooses another", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("combobox", { name: "Vital sign" }));
    expect(screen.getByRole("option", { name: /SpO₂/ })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("option", { name: /Temperature/ }));
    expect(screen.getByText("temperature", { selector: "output" })).toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveTextContent("Temperature");
  });

  it("works from the keyboard: arrows skip disabled options, Enter chooses, Esc closes", async () => {
    render(<Harness />);
    const box = screen.getByRole("combobox");
    box.focus();
    await userEvent.keyboard("{ArrowDown}"); // opens on the selected option (SpO₂)
    expect(box).toHaveAttribute("aria-expanded", "true");
    await userEvent.keyboard("{ArrowDown}{ArrowDown}"); // Temperature, then Weight is disabled
    expect(box.getAttribute("aria-activedescendant")).toBe(
      screen.getByRole("option", { name: /Temperature/ }).id,
    );
    await userEvent.keyboard("{Enter}");
    expect(box).toHaveTextContent("Temperature");
    expect(box).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}{Escape}");
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(box).toHaveTextContent("Temperature");
  });

  it("jumps to an option by typing its first letters", async () => {
    render(<Harness />);
    screen.getByRole("combobox").focus();
    await userEvent.keyboard("h");
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("combobox")).toHaveTextContent("Heart rate");
  });

  it("adds a search field to long lists and filters by label, description and keywords", async () => {
    const patients: SelectOption[] = Array.from({ length: 12 }, (_, i) => ({
      value: `p${i}`,
      label: i === 7 ? "Keller, Anna" : `Patient ${i}`,
      description: `Room 30${i}`,
      keywords: i === 7 ? "SYN-042-0001" : undefined,
    }));
    render(<Harness options={patients} initial="p0" />);
    await userEvent.click(screen.getByRole("combobox"));
    const search = screen.getByRole("searchbox");
    expect(search).toHaveFocus();
    await userEvent.type(search, "0001");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("combobox")).toHaveTextContent("Keller, Anna");
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText(/No matches/)).toBeInTheDocument();
  });

  it("closes on an outside click without changing the value", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(document.body);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveTextContent("SpO₂");
  });
});

describe("matches", () => {
  it("ignores case and accents and needs every word", () => {
    const o = { value: "x", label: "Zoë Müller", description: "Room 302a" };
    expect(matches(o, "zoe muller")).toBe(true);
    expect(matches(o, "302a muller")).toBe(true);
    expect(matches(o, "301")).toBe(false);
  });
});
