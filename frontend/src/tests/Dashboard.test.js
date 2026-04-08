// src/tests/Dashboard.test.js
import { render, screen } from "@testing-library/react";
import Dashboard from "../components/Dashboard";

test("displays dashboard cards", () => {
  render(<Dashboard />);

  expect(screen.getByText(/total income/i)).toBeInTheDocument();
  expect(screen.getByText(/total expenses/i)).toBeInTheDocument();
});