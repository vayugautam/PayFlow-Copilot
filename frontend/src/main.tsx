import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import { Providers } from "./app/providers";
import { AuthProvider } from "./features/auth/AuthContext";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><BrowserRouter><Providers><AuthProvider><App /></AuthProvider></Providers></BrowserRouter></React.StrictMode>);
