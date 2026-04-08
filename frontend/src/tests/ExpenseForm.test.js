// src/tests/ExpenseForm.test.js
import { render, screen, fireEvent } from "@testing-library/react";
import ExpenseForm from "../components/ExpenseForm";

test("validates amount field", () => {
  render(<ExpenseForm />);

  fireEvent.change(screen.getByLabelText(/amount/i), {
    target: { value: "" },
  });

  fireEvent.click(screen.getByText(/submit/i));

  expect(screen.getByText(/amount is required/i)).toBeInTheDocument();
});