"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { loginUser, registerUser } from "../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        const { error: regErr } = await registerUser(email, password, name);
        if (regErr) {
          setError(regErr);
          setLoading(false);
          return;
        }
        router.push("/onboarding");
      } else {
        const { error: logErr } = await loginUser(email, password);
        if (logErr) {
          setError(logErr);
          setLoading(false);
          return;
        }
        router.push("/app");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
      setLoading(false);
    }
  };

  return (
    <main id="main" style={{ maxWidth: "480px" }}>
      <p className="eyebrow">AegisOps / Authentication</p>
      <div className="heading" style={{ marginBottom: "20px" }}>
        <h1>{isRegister ? "Create account" : "Sign in"}</h1>
      </div>

      <div className="panel" style={{ marginTop: "0" }}>
        <div
          style={{
            display: "flex",
            gap: "12px",
            marginBottom: "24px",
            borderBottom: "1px solid #30383a",
            paddingBottom: "12px",
          }}
        >
          <button
            type="button"
            onClick={() => {
              setIsRegister(false);
              setError(null);
            }}
            style={{
              background: "none",
              border: "none",
              color: !isRegister ? "#c9e6a0" : "#9eaeb2",
              fontWeight: !isRegister ? 700 : 400,
              cursor: "pointer",
              fontSize: "14px",
              padding: "4px 8px",
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => {
              setIsRegister(true);
              setError(null);
            }}
            style={{
              background: "none",
              border: "none",
              color: isRegister ? "#c9e6a0" : "#9eaeb2",
              fontWeight: isRegister ? 700 : 400,
              cursor: "pointer",
              fontSize: "14px",
              padding: "4px 8px",
            }}
          >
            Register
          </button>
        </div>

        {error && (
          <div
            style={{
              background: "#2d1616",
              border: "1px solid #6b2828",
              color: "#f87171",
              padding: "10px 14px",
              borderRadius: "5px",
              fontSize: "13px",
              marginBottom: "16px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor="name-input"
                style={{
                  display: "block",
                  fontSize: "12px",
                  marginBottom: "6px",
                  color: "#9eaeb2",
                }}
              >
                Full Name
              </label>
              <input
                id="name-input"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Developer"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  background: "#101416",
                  border: "1px solid #343e40",
                  borderRadius: "5px",
                  color: "#edf1f2",
                  fontSize: "14px",
                }}
              />
            </div>
          )}

          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="email-input"
              style={{
                display: "block",
                fontSize: "12px",
                marginBottom: "6px",
                color: "#9eaeb2",
              }}
            >
              Work Email
            </label>
            <input
              id="email-input"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@company.com"
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "#101416",
                border: "1px solid #343e40",
                borderRadius: "5px",
                color: "#edf1f2",
                fontSize: "14px",
              }}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label
              htmlFor="password-input"
              style={{
                display: "block",
                fontSize: "12px",
                marginBottom: "6px",
                color: "#9eaeb2",
              }}
            >
              Password
            </label>
            <input
              id="password-input"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "#101416",
                border: "1px solid #343e40",
                borderRadius: "5px",
                color: "#edf1f2",
                fontSize: "14px",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="button"
            style={{
              width: "100%",
              justifyContent: "center",
              marginTop: "0",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading
              ? "Authenticating..."
              : isRegister
                ? "Create workspace"
                : "Sign in"}
          </button>
        </form>

        <div
          style={{
            marginTop: "20px",
            textAlign: "center",
            fontSize: "12px",
            color: "#9eaeb2",
          }}
        >
          Demo instance:{" "}
          <Link href="/app" style={{ color: "#aedcd0" }}>
            Enter as demo guest
          </Link>
        </div>
      </div>
    </main>
  );
}
