import { useState } from "react";
import { Field } from "@/components/Field";
import { Logo } from "@/components/Logo";
import { EyeIcon, EyeOffIcon } from "@/components/icons";
import { inputStyle } from "@/lib/ui";

export function LoginScreen({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      await onLogin(email, password);
      // success: the app switches away from this screen
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#F9F7F5" }}>
      {/* Logo at top */}
      <div style={{ paddingTop: "calc(env(safe-area-inset-top) + 48px)", paddingBottom: "48px", display: "flex", justifyContent: "center", flexShrink: 0 }}>
        <Logo height={110} />
      </div>

      {/* Form */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 24px calc(env(safe-area-inset-bottom) + 32px)", maxWidth: 420, width: "100%", alignSelf: "center" }}>

        <h2 style={{ fontFamily: "Outfit, sans-serif", fontSize: 26, fontWeight: 700, color: "#2C2420", marginBottom: 6 }}>Welcome back</h2>
        <p style={{ color: "#9B9390", fontSize: 15, marginBottom: 32, fontFamily: "Outfit, sans-serif" }}>Sign in to access your health records</p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <Field label="Email address">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required style={inputStyle} />
          </Field>
          <Field label="Password">
            <div style={{ position: "relative" }}>
              <input type={showPw ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required style={{ ...inputStyle, paddingRight: 46 }} />
              <button type="button" onClick={() => setShowPw(v => !v)} style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "#9B9390", padding: 0, display: "flex" }}>
                {showPw ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </Field>
          {error && <p style={{ color: "#E07B55", fontSize: 13, fontFamily: "Outfit, sans-serif", marginTop: -8 }}>{error}</p>}
          <div style={{ textAlign: "right", marginTop: -8 }}>
            <a href="#" style={{ color: "#E07B55", fontSize: 14, fontFamily: "Outfit, sans-serif", textDecoration: "none", fontWeight: 500 }}>Forgot password?</a>
          </div>
          <button type="submit" disabled={loading} style={{ marginTop: 4, padding: "16px", background: loading ? "#F0A888" : "#E07B55", color: "#fff", border: "none", borderRadius: 14, fontFamily: "Outfit, sans-serif", fontSize: 17, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", transition: "background 0.2s" }}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div style={{ marginTop: 28, textAlign: "center" }}>
          <span style={{ color: "#9B9390", fontSize: 14, fontFamily: "Outfit, sans-serif" }}>Don't have an account? </span>
          <a href="#" style={{ color: "#7BAAC8", fontSize: 14, fontWeight: 600, fontFamily: "Outfit, sans-serif", textDecoration: "none" }}>Sign up</a>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 24, marginBottom: 16 }}>
          <div style={{ flex: 1, height: 1, background: "#EDE9E5" }} />
          <span style={{ color: "#C4BDB9", fontSize: 13, fontFamily: "Outfit, sans-serif" }}>or continue with</span>
          <div style={{ flex: 1, height: 1, background: "#EDE9E5" }} />
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          {["Google", "Apple"].map(p => (
            <button key={p} style={{ flex: 1, padding: "14px", background: "#fff", border: "1.5px solid #EDE9E5", borderRadius: 13, fontFamily: "Outfit, sans-serif", fontSize: 15, fontWeight: 500, color: "#2C2420", cursor: "pointer" }}>{p}</button>
          ))}
        </div>

      </div>

    </div>
  );
}
