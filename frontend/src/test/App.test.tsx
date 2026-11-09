import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "../features/auth/AuthContext";
import { App } from "../app/App";
import { queryClient } from "../lib/query-client";

describe("application foundation", () => {
  it("redirects unauthenticated users to login", async () => {
    sessionStorage.clear();
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/dashboard"]}><AuthProvider><App /></AuthProvider></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText("Welcome back")).toBeInTheDocument();
  });
});
