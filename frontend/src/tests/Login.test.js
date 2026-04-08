// src/tests/Login.test.js
import { render, screen, fireEvent } from "@testing-library/react";
import Login from "../components/Login";

test("renders login form fields", () => {
  render(<Login />);

  expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
});

test("validates empty form submission", () => {
  render(<Login />);

  fireEvent.click(screen.getByText(/login/i));

  expect(screen.getByText(/required/i)).toBeInTheDocument();
});